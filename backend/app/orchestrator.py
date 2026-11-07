"""The turn loop: guardrails -> active agent -> tools -> handoffs -> output guardrail.

Two things worth knowing:

1. A handoff is just a tool call (`transfer_to_journey`). When one happens we swap
   the system prompt and the tool set and keep looping with the same message list, so
   the new agent inherits everything the previous one found out.
2. If the LLM is unavailable, slow or broken, `_template_turn` plays the same turn
   deterministically from real tool results (PLAN §5 D6). The demo therefore runs
   end to end with no API key at all — the replies are just blunter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import agents, guardrails, llm, timetable, tools
from .models import AgentName, GuardrailEvent
from .state import SessionState, advance_phase, transport_in_message

MAX_ROUNDS = 6


@dataclass
class TurnResult:
    reply: str | None
    agent: AgentName
    events: list[GuardrailEvent] = field(default_factory=list)
    open_panel: str | None = None
    used_llm: bool = True


def _panel_for(state: SessionState) -> str | None:
    """A suggestion only — the user can always override it (PLAN §4.3)."""
    if state.phase == "indoor" and state.indoor_route:
        return "floorplan"
    if state.phase == "outdoor" and state.outdoor_route:
        return "map"
    return None


def run_turn(state: SessionState, message: str) -> TurnResult:
    state.remember("user", message)

    # --- stage 1: input guardrail (F8) ---
    verdict = guardrails.input_guardrail(message, state)
    events = list(verdict.events)

    if verdict.refusal:
        state.remember("assistant", verdict.refusal)
        return TurnResult(verdict.refusal, state.active_agent, events, used_llm=False)

    if verdict.escalate:
        # Human-in-the-loop is too important to leave to the model's discretion (F9).
        tools.escalate_to_human(state, verdict.escalate)
        reply = (state.escalation or {}).get("message", "Shall I get someone to help you?")
        state.remember("assistant", reply)
        return TurnResult(reply, state.active_agent, events, used_llm=False)

    # What the user just said about how they are travelling beats a stale Settings
    # toggle — the one-tap chips send exactly "I'll take the bus" / "I'll walk".
    named_mode = transport_in_message(message)
    if named_mode:
        state.spoken_transport = named_mode  # type: ignore[assignment]

    # --- the phase machine, before the LLM, so mode-switching is deterministic (F12) ---
    advance_phase(state, message)

    if verdict.reask_position and not llm.available():
        # Repeating the step they are already stuck on is the one answer that is no
        # use here, and it is what the template path would otherwise give.
        reply = (
            "Let's get you back on track. What can you see around you — a lift, "
            "a door, or a room number?"
        )
        state.remember("assistant", reply)
        return TurnResult(reply, state.active_agent, events, used_llm=False)

    if not llm.available():
        return _template_turn(state, message, events)

    # --- stage 2: the agent loop ---
    messages: list[dict] = [dict(turn) for turn in state.history]

    for _ in range(MAX_ROUNDS):
        agent = agents.AGENTS[state.active_agent]
        result = llm.chat(
            model=agent.model,
            system=agent.system(state),
            messages=messages,
            tools=agent.schemas(),
        )

        if not result.ok:
            fallback = _template_turn(state, message, events)
            fallback.used_llm = False
            return fallback

        if not result.tool_calls:
            reply, output_events = guardrails.output_guardrail(
                result.text or "", state, fallback=lambda: _template_reply(state, message)
            )
            events.extend(output_events)
            state.remember("assistant", reply)
            return TurnResult(reply, state.active_agent, events, _panel_for(state))

        # The model asked for tools. Echo its message, then answer every call —
        # a tool_call left without a result is a protocol error on the next round.
        messages.append(
            {
                "role": "assistant",
                "content": result.text,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": json.dumps(call.args)},
                    }
                    for call in result.tool_calls
                ],
            }
        )

        for call in result.tool_calls:
            target = agents.handoff_target(call.name)
            if target:
                # Worth a log line: a model-initiated handoff is the multi-agent
                # system doing its job, and otherwise it leaves no trace anywhere
                # except the agent name on the final reply.
                print(f"[handoff] {state.active_agent} -> {target} ({state.session_id})")
                state.active_agent = target
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(
                            {"ok": True, "note": f"You are now the {target} agent."}
                        ),
                    }
                )
                continue

            implementation = tools.IMPLEMENTATIONS.get(call.name)
            if implementation is None:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps({"ok": False, "note": "No such tool."}),
                    }
                )
                continue

            # --- stage 2 guardrail: validate and if needed rewrite the arguments ---
            try:
                args, tool_events = guardrails.tool_guardrail(call.name, call.args, state, message)
                events.extend(tool_events)
                output = implementation(state, **args)
            except guardrails.ToolBlocked as blocked:
                events.append(blocked.event)
                output = {"ok": False, "note": blocked.reply_to_model}
            except TypeError as exc:  # the model passed arguments the tool does not take
                output = {"ok": False, "note": f"Wrong arguments for {call.name}: {exc}"}
            except Exception as exc:  # noqa: BLE001 - a tool must never 500 the chat
                print(f"[orchestrator] tool {call.name} failed: {type(exc).__name__}: {exc}")
                output = {"ok": False, "note": "That didn't work. Tell the student plainly."}

            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps(output, default=str)}
            )

    # Ran out of rounds: answer from what the tools already found.
    exhausted = _template_turn(state, message, events)
    exhausted.events.append(
        GuardrailEvent(
            stage="output",
            rule="tool_loop_limit",
            action="modified",
            message=f"Stopped after {MAX_ROUNDS} tool rounds and answered from the results.",
        )
    )
    return exhausted


# --- D6: the same turn, without the LLM -------------------------------------------


def _as_list(options: list[str]) -> str:
    """"a, b or c" — it gets read aloud, so no trailing "or" on every item."""
    if len(options) <= 1:
        return options[0] if options else ""
    return f"{', '.join(options[:-1])} or {options[-1]}"


def _current_step_text(state: SessionState) -> str | None:
    """The one step the student is on — one instruction at a time (F7)."""
    steps = (state.indoor_route or {}).get("steps") or []
    index = state.current_step or 0
    if 0 <= index < len(steps):
        return str(steps[index].get("instruction") or "")
    return None


def _template_reply(state: SessionState, message: str) -> str:
    """One deterministic reply built only from real tool results."""
    if state.next_class is None:
        tools.get_next_class(state)
    next_class = state.next_class

    if state.phase == "arrived":
        room = (next_class or {}).get("room_label")
        return (
            f"You've made it to {room}. Hope the lecture goes well."
            if room
            else "You've arrived. Hope it goes well."
        )

    if state.phase == "indoor":
        if state.current_node is None:
            found = tools.locate_user(state, message)
            if not found.get("found"):
                options = [
                    str(item.get("label"))
                    for item in found.get("candidates", [])
                    if item.get("label")
                ]
                if options:
                    # Candidates can be entrances, lifts, stairwells or rooms, so the
                    # question has to be neutral about what they are.
                    return f"Which of these are you nearest to: {_as_list(options[:3])}?"
                return "Whereabouts in the building are you? Tell me the nearest door or lift."

        if state.indoor_route is None and next_class:
            tools.plan_indoor_route(state, state.current_node or "", next_class.get("room_id", ""))

        step = _current_step_text(state)
        if step:
            # Reassure a step-free user once, on the first step — not glued to every
            # instruction, where it ends up on steps that involve no lift at all.
            steps = (state.indoor_route or {}).get("steps") or []
            first = (state.current_step or 0) == 0
            uses_lift = any(item.get("via") == "lift" for item in steps)
            prefix = "This route is step-free, using the lift. " if (
                state.no_stairs and first and uses_lift
            ) else ""
            return f"{prefix}{step}"
        return "I can't work out a route inside the building right now."

    if state.phase == "outdoor":
        # What they just said wins; the Settings toggle is only the default.
        mode = transport_in_message(message) or state.transport
        if mode is None:
            lead = ""
            if next_class:
                lead = (
                    f"Your next class is {next_class['title']} "
                    f"{timetable.human_when(next_class, state.now())}, in "
                    f"{next_class['room_label']}. "
                )
            return f"{lead}How would you like to travel: walk, run, or take the bus?"

        planned = tools.plan_outdoor_route(state, mode)
        if planned.get("ok") and state.outdoor_route:
            route = state.outdoor_route
            urgency = {
                "late": "You're already running late.",
                "hurry": "You need to hurry.",
                "on_time": "You're on time.",
            }.get(route["status"], "")
            return (
                f"{route['summary']}. Leave at "
                f"{timetable.local_time(route['leave_at'])}. {urgency}".strip()
            )
        if mode == "bus":
            return "I can't check live bus times right now. Walking is the reliable option."
        return "I can't work out that journey at the moment."

    if next_class:
        when = timetable.human_when(next_class, state.now())
        return (
            f"Your next class is {next_class['title']} {when}, in "
            f"{next_class['room_label']}. How would you like to get there?"
        )

    return "I couldn't find a class in your timetable. What room are you trying to get to?"


def _template_turn(
    state: SessionState, message: str, events: list[GuardrailEvent]
) -> TurnResult:
    reply = _template_reply(state, message)
    reply, output_events = guardrails.output_guardrail(reply, state, fallback=reply)
    events = [*events, *output_events]
    state.remember("assistant", reply)
    return TurnResult(reply, state.active_agent, events, _panel_for(state), used_llm=False)
