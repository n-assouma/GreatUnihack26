"""The three specialised agents (F2).

Each one has a role prompt, its own set of tools and the handoffs it is allowed to
make. The orchestrator picks the active agent from the phase, and a handoff is just
another tool call — which is what makes it visible in `ChatResponse.agent` and
provable in the demo.

The state summary is appended to every system prompt, so an agent that takes over
mid-conversation knows what the previous one already worked out.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import llm, timetable, tools
from .models import AgentName
from .state import SessionState

SHARED_RULES = """You are part of Find My Way, an assistant that gets University of \
Manchester students to the right classroom on time. You are talking to one student.

How to speak:
- Plain English, 1 to 3 short sentences. Your reply is read aloud, so no lists, no \
markdown, no emoji, and never read out a code or an id.
- Say only what a tool actually returned. If you do not have something, say you will \
find out or ask for it. Never invent a room, a room code, a bus line, a time or a \
phone number.
- One question at a time.

Hard rules:
- You never work out a route yourself. Call a tool and explain what it gives back.
- You never draw or describe a map image; the screen shows it.
- If the student cannot use stairs, never mention stairs: they take the lift.
- If you are not the right agent for what they asked, hand over straight away."""

VISUAL_IMPAIRMENT_RULES = """
This student uses a screen reader or cannot see the screen well. Describe landmarks \
they can feel or hear and give distances in metres and paces. Never say "as you can \
see on the screen"."""

ROLE_PROMPTS: dict[AgentName, str] = {
    "coordinator": """You are the Coordinator.

You greet the student, tell them about their next class, and answer general questions \
about getting around campus. You are the first point of contact.

Hand over as soon as the subject is clear:
- They want to get to the building, or ask about the bus, walking, running, leaving \
time or being late -> transfer_to_journey.
- They are at or inside the Nancy Rothwell Building, or ask for directions to a room, \
an entrance, a floor or a lift -> transfer_to_indoor.

If they are lost, hurt or ask for a person, call escalate_to_human.""",
    "journey": """You are the Journey agent.

You get the student from where they are to the Nancy Rothwell Building, on time.

First agree how they are travelling: walking, running or the bus. If they have not \
said, ask, and offer those three. Then call plan_outdoor_route with that mode and tell \
them the one thing that matters most: when to leave, and whether they are on time, \
need to hurry, or are already late.

If the bus cannot be checked, say so plainly and offer walking. Never invent a bus \
line, a stop or a departure time.

Once they reach the building, transfer_to_indoor.""",
    "indoor": """You are the Indoor agent, inside the Nancy Rothwell Building.

Work in this order:
1. If you do not know where the student is, ask, then call locate_user with their own \
words. If it comes back unclear, offer at most three named places and ask which.
2. Call plan_indoor_route to get the steps.
3. Give them ONE step at a time, the one they are on. Say the floor when it changes, \
and name the lift when they need it. Wait for them to move before the next step.

Use landmarks they can see, not compass bearings. If 'left' or 'right' would be \
ambiguous and you do not know which way they face, ask what is in front of them and \
call set_facing.

If they say they are lost, do not repeat the step they are stuck on. Ask what they \
can see around them — a lift, a door, a room number — and call locate_user with the \
answer to work out where they are now.

If they tell you they are lost a second time, or are hurt and stuck, call \
escalate_to_human.""",
}


@dataclass
class Agent:
    name: AgentName
    role: str
    tool_names: list[str] = field(default_factory=list)
    handoffs: list[AgentName] = field(default_factory=list)

    @property
    def model(self) -> str:
        return llm.main_model()

    def schemas(self) -> list[dict]:
        return tools.schemas_for(self.tool_names, self.handoffs)

    def system(self, state: SessionState) -> str:
        parts = [SHARED_RULES]
        if state.visual_impairment:
            parts.append(VISUAL_IMPAIRMENT_RULES)
        parts.append(self.role)
        parts.append(state_summary(state))
        return "\n\n".join(parts)


def state_summary(state: SessionState) -> str:
    """What this agent already knows. Kept short — it is in every request."""
    lines = [f"Right now ({'demo clock' if state.demo_mode else 'live'} "
             f"{state.now():%a %H:%M}):"]

    next_class = state.next_class
    if next_class:
        lines.append(
            f"- Next class: {next_class['title']} "
            f"{timetable.human_when(next_class, state.now())}, {next_class['room_label']}"
            + (" (this building)" if next_class["building_id"] == "nancy_rothwell"
               else " (a different building)")
        )
    else:
        lines.append("- Next class: not looked up yet; call get_next_class.")

    lines.append(f"- Phase: {state.phase}")

    if state.no_stairs:
        lines.append("- ACCESSIBILITY: cannot use stairs. Lifts only. Never mention stairs.")
    if state.visual_impairment:
        lines.append("- ACCESSIBILITY: visually impaired. Describe landmarks and distances.")

    if state.transport_pref:
        lines.append(f"- Travelling by: {state.transport_pref}")
    if state.outdoor_route:
        lines.append(
            f"- Journey planned: {state.outdoor_route['summary']} "
            f"(leave {timetable.local_time(state.outdoor_route['leave_at'])}, "
            f"{state.outdoor_route['status']})"
        )

    if state.current_node:
        floor = f", floor {state.current_floor}" if state.current_floor is not None else ""
        lines.append(f"- The student is at: {state.current_node}{floor}")
    else:
        lines.append("- Where the student is: unknown.")

    if state.heading_source == "entrance":
        lines.append("- Facing: into the building through that entrance (left/right are safe).")
    elif state.heading_source in ("compass", "spoken") and state.heading is not None:
        lines.append(f"- Facing: {round(state.heading)} degrees ({state.heading_source}).")

    if state.indoor_route:
        steps = state.indoor_route.get("steps", [])
        index = state.current_step or 0
        if 0 <= index < len(steps):
            lines.append(
                f"- Indoor route: step {index + 1} of {len(steps)}: "
                f"\"{steps[index].get('instruction')}\""
            )
        else:
            lines.append(f"- Indoor route: {len(steps)} steps planned.")

    if state.lost_count:
        lines.append(f"- The student has said they are lost {state.lost_count} time(s).")

    return "\n".join(lines)


AGENTS: dict[AgentName, Agent] = {
    "coordinator": Agent(
        name="coordinator",
        role=ROLE_PROMPTS["coordinator"],
        tool_names=["get_next_class", "escalate_to_human"],
        handoffs=["journey", "indoor"],
    ),
    "journey": Agent(
        name="journey",
        role=ROLE_PROMPTS["journey"],
        tool_names=["get_next_class", "plan_outdoor_route", "escalate_to_human"],
        handoffs=["coordinator", "indoor"],
    ),
    "indoor": Agent(
        name="indoor",
        role=ROLE_PROMPTS["indoor"],
        tool_names=[
            "locate_user",
            "set_facing",
            "plan_indoor_route",
            "get_next_class",
            "escalate_to_human",
        ],
        handoffs=["coordinator"],
    ),
}

HANDOFF_PREFIX = "transfer_to_"


def handoff_target(tool_name: str) -> AgentName | None:
    if not tool_name.startswith(HANDOFF_PREFIX):
        return None
    target = tool_name[len(HANDOFF_PREFIX) :]
    return target if target in AGENTS else None  # type: ignore[return-value]
