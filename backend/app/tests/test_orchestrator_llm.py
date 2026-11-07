"""The LLM path, driven by a scripted model instead of a real one.

Without these, the agent loop, the handoffs and the tool-argument plumbing would
only ever run once a real ANTHROPIC_API_KEY lands — which on a hackathon day could
easily be minutes before the demo. A scripted `llm.chat` exercises exactly the code
the real key will hit, offline and for free.
"""

from __future__ import annotations

import os

import pytest

os.environ["MOCK_LLM"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app import llm  # noqa: E402
from app.main import app  # noqa: E402
from app.models import BUILDING_LAT, BUILDING_LNG  # noqa: E402
from app.state import get_session, reset_sessions  # noqa: E402

client = TestClient(app)

PLAIN = {"accessibility": {"no_stairs": False, "visual_impairment": False}}
NO_STAIRS = {"accessibility": {"no_stairs": True, "visual_impairment": False}}
AT_BUILDING = {"lat": BUILDING_LAT, "lng": BUILDING_LNG}


class ScriptedLLM:
    """Returns canned LlmResults in order and records what it was asked."""

    def __init__(self, *script: llm.LlmResult) -> None:
        self.script = list(script)
        self.calls: list[dict] = []

    def __call__(self, model, system, messages, tools=None, timeout=20):  # noqa: ANN001
        self.calls.append(
            {
                "system": system,
                "messages": [dict(message) for message in messages],
                "tool_names": [tool["function"]["name"] for tool in (tools or [])],
            }
        )
        if not self.script:
            return llm.LlmResult(ok=True, text="(script exhausted)")
        return self.script.pop(0)


@pytest.fixture(autouse=True)
def _clean_sessions():
    reset_sessions()
    yield
    reset_sessions()


@pytest.fixture
def scripted(monkeypatch):
    def install(*script: llm.LlmResult) -> ScriptedLLM:
        fake = ScriptedLLM(*script)
        monkeypatch.setattr(llm, "available", lambda: True)
        monkeypatch.setattr(llm, "chat", fake)
        monkeypatch.setattr(llm, "classify", lambda system, text: {"category": "on_topic"})
        return fake

    return install


def call(message: str, context: dict, session_id: str = "s-llm") -> dict:
    response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": message, "context": context},
    )
    assert response.status_code == 200, response.text
    return response.json()


def tool_call(name: str, args: dict | None = None, call_id: str = "c1") -> llm.ToolCall:
    return llm.ToolCall(id=call_id, name=name, args=args or {})


def test_a_handoff_swaps_the_agent_its_prompt_and_its_tools(scripted):
    """F2: the coordinator hands to journey, which then has journey's tools."""
    fake = scripted(
        llm.LlmResult(ok=True, tool_calls=[tool_call("transfer_to_journey")]),
        llm.LlmResult(ok=True, tool_calls=[tool_call("plan_outdoor_route", {"mode": "walk"}, "c2")]),
        llm.LlmResult(ok=True, text="Leave now and you'll get there with time to spare."),
    )

    # A plain greeting, so the phase machine leaves us with the coordinator and the
    # handoff is genuinely the model's decision rather than a phase transition.
    body = call("hello there", {**PLAIN, "lat": 53.46, "lng": -2.23})

    assert body["agent"] == "journey"
    assert body["reply"] == "Leave now and you'll get there with time to spare."

    # Round 1 was the coordinator: it can hand off but cannot plan a journey itself.
    assert "transfer_to_journey" in fake.calls[0]["tool_names"]
    assert "plan_outdoor_route" not in fake.calls[0]["tool_names"]
    # Round 2 is the journey agent, with its own tools and its own role prompt.
    assert "plan_outdoor_route" in fake.calls[1]["tool_names"]
    assert "You are the Journey agent" in fake.calls[1]["system"]

    # Every tool_call got a matching tool result — a missing one is a protocol error.
    tool_results = [m for m in fake.calls[2]["messages"] if m.get("role") == "tool"]
    assert len(tool_results) == 2
    assert {m["tool_call_id"] for m in tool_results} == {"c1", "c2"}


def test_the_model_asking_for_stairs_still_gets_an_accessible_route(scripted):
    """F5: the guardrail overrules the model, and the override is visible as a badge."""
    scripted(
        llm.LlmResult(
            ok=True,
            tool_calls=[
                tool_call(
                    "plan_indoor_route", {"start": "entrance_east", "destination": "THEATRE_A"}
                )
            ],
        ),
        llm.LlmResult(ok=True, text="Head for the lift and go up to the first floor."),
    )
    client.post("/api/tick", json={"session_id": "s-llm", "context": {**NO_STAIRS, **AT_BUILDING}})

    body = call("I'm at the east entrance", {**NO_STAIRS, **AT_BUILDING})

    route = body["ui"]["indoor_route"]
    assert route is not None, body
    assert route["accessible"] is True
    assert all(step.get("via") != "stairs" for step in route["steps"])
    assert any(
        e["rule"] == "no_stairs_enforced" and e["action"] == "modified" for e in body["guardrails"]
    )


def test_an_invented_room_is_refused_and_the_model_is_told_why(scripted):
    """The model never gets to route to a room that does not exist."""
    fake = scripted(
        llm.LlmResult(
            ok=True,
            tool_calls=[
                tool_call("plan_indoor_route", {"start": "entrance_east", "destination": "9Z.999"})
            ],
        ),
        llm.LlmResult(ok=True, text="Which room do you need?"),
    )
    client.post("/api/tick", json={"session_id": "s-llm", "context": {**PLAIN, **AT_BUILDING}})

    body = call("take me to room 9Z.999", {**PLAIN, **AT_BUILDING})

    assert any(e["rule"] == "unknown_room" and e["action"] == "blocked" for e in body["guardrails"])
    # The refusal is fed back as the tool result, so the model can ask rather than guess.
    tool_results = [m for m in fake.calls[1]["messages"] if m.get("role") == "tool"]
    assert "does not exist" in tool_results[0]["content"]


def test_a_destination_the_user_never_asked_for_is_corrected_to_the_class_room(scripted):
    scripted(
        llm.LlmResult(
            ok=True,
            tool_calls=[
                tool_call("plan_indoor_route", {"start": "entrance_east", "destination": "3A.041"})
            ],
        ),
        llm.LlmResult(ok=True, text="Take the lift to the first floor."),
    )
    state = get_session("s-llm")
    state.next_class = {
        "title": "COMP15111 (Drop-in)",
        "start": "2026-11-09T10:00:00+00:00",
        "end": "2026-11-09T11:00:00+00:00",
        "building_id": "nancy_rothwell",
        "room_id": "THEATRE_A",
        "room_label": "Lecture Theatre A",
    }
    client.post("/api/tick", json={"session_id": "s-llm", "context": {**PLAIN, **AT_BUILDING}})

    body = call("where do I go?", {**PLAIN, **AT_BUILDING})

    assert body["ui"]["indoor_route"]["destination_id"] == "THEATRE_A"
    assert any(e["rule"] == "destination_corrected" for e in body["guardrails"])


def test_an_invented_bus_line_in_the_reply_is_stripped(scripted):
    """PLAN §4.5: the model may not state a bus line no tool returned."""
    scripted(llm.LlmResult(ok=True, text="Take bus 142 from Oxford Road, it gets you there by 8:52."))

    body = call("how do I get there by bus?", {**PLAIN, "lat": 53.46, "lng": -2.23})

    assert "142" not in (body["reply"] or "")
    assert any(e["rule"] == "unverified_detail" for e in body["guardrails"])


def test_a_rambling_reply_is_shortened_because_it_gets_spoken(scripted):
    scripted(llm.LlmResult(ok=True, text="So " + "walk along the corridor and then " * 20))

    body = call("where do I go?", {**PLAIN, "lat": 53.46, "lng": -2.23})

    assert len(body["reply"].split()) <= 61
    assert any(e["rule"] == "too_long" for e in body["guardrails"])


def test_the_tool_loop_cannot_spin_forever(scripted):
    """A model that only ever calls tools must still produce a reply."""
    looping = [
        llm.LlmResult(ok=True, tool_calls=[tool_call("get_next_class", {}, f"c{i}")])
        for i in range(10)
    ]
    scripted(*looping)

    body = call("what's my next class?", {**PLAIN, "lat": 53.46, "lng": -2.23})

    assert body["reply"]
    assert any(e["rule"] == "tool_loop_limit" for e in body["guardrails"])


def test_each_agent_sees_the_state_the_previous_one_worked_out(scripted):
    """A handoff must not lose context: the indoor agent inherits the position."""
    fake = scripted(
        llm.LlmResult(ok=True, tool_calls=[tool_call("locate_user", {"text": "east entrance"})]),
        llm.LlmResult(ok=True, tool_calls=[tool_call("transfer_to_coordinator", {}, "c2")]),
        llm.LlmResult(ok=True, text="Anything else?"),
    )
    client.post("/api/tick", json={"session_id": "s-llm", "context": {**PLAIN, **AT_BUILDING}})

    call("I'm at the east entrance", {**PLAIN, **AT_BUILDING})

    assert "entrance_east" in fake.calls[-1]["system"]
    assert "Facing: into the building" in fake.calls[-1]["system"]


@pytest.mark.parametrize(
    "message",
    [
        "take me to room 9Z.999",  # "999" used to match the emergency keyword
        "help with my machine learning skills",  # "kill" used to match inside "skills"
        "where is the lecture about steel structures",  # "steal"
    ],
)
def test_keywords_match_whole_words_only(scripted, message):
    """Regression: substring matching made innocent messages escalate or get refused."""
    scripted(llm.LlmResult(ok=True, text="Let me check that for you."))

    body = call(message, {**PLAIN, "lat": 53.46, "lng": -2.23})

    assert body["phase"] != "escalated", body
    assert body["ui"]["escalation"] is None
    assert not [e for e in body["guardrails"] if e["action"] == "blocked"], body["guardrails"]


def test_an_ambiguous_location_does_not_escalate_on_its_own(scripted):
    """With the real graph "by the lifts" is a reasonable answer that comes back
    ambiguous. Asking "which lift?" twice must not offer to call reception."""
    scripted(
        llm.LlmResult(ok=True, tool_calls=[tool_call("locate_user", {"text": "by the lifts"})]),
        llm.LlmResult(ok=True, text="Which lift core are you at?"),
        llm.LlmResult(ok=True, tool_calls=[tool_call("locate_user", {"text": "by the lifts"}, "c2")]),
        llm.LlmResult(ok=True, text="Is it the one by the main doors?"),
    )
    client.post("/api/tick", json={"session_id": "s-amb", "context": {**PLAIN, **AT_BUILDING}})

    call("I'm by the lifts", {**PLAIN, **AT_BUILDING}, session_id="s-amb")
    body = call("by the lifts", {**PLAIN, **AT_BUILDING}, session_id="s-amb")

    assert body["phase"] != "escalated", body
    assert body["ui"]["escalation"] is None
    assert get_session("s-amb").lost_count >= 1  # still counted as a signal


def test_saying_lost_once_then_an_unresolvable_location_does_escalate(scripted):
    """Distress plus a position we cannot pin down is when a human is warranted."""
    scripted(
        llm.LlmResult(ok=True, tool_calls=[tool_call("locate_user", {"text": "no idea"})]),
        llm.LlmResult(ok=True, text="Can you see a lift or a door?"),
    )
    client.post("/api/tick", json={"session_id": "s-esc", "context": {**PLAIN, **AT_BUILDING}})

    call("I'm lost", {**PLAIN, **AT_BUILDING}, session_id="s-esc")  # said_lost = 1
    body = call("somewhere near a corridor", {**PLAIN, **AT_BUILDING}, session_id="s-esc")

    state = get_session("s-esc")
    assert state.lost_count >= 2 and state.said_lost_count == 1
    # The next distress signal escalates.
    final = call("I'm lost", {**PLAIN, **AT_BUILDING}, session_id="s-esc")
    assert final["ui"]["escalation"] is not None, final


def test_an_injury_the_classifier_calls_an_emergency_still_gets_a_route(monkeypatch):
    """A3's real-key bug, and it broke demo step 4 outright. A real classifier reads
    "I hurt my ankle" as an emergency; the keyword stage has already judged that an
    injury mentioned while asking for directions is an accessibility need. The code's
    decision wins, and the override is visible as a badge."""
    fake = ScriptedLLM(
        llm.LlmResult(
            ok=True,
            tool_calls=[tool_call("locate_user", {"text": "East entrance"})],
        ),
        llm.LlmResult(
            ok=True,
            tool_calls=[
                tool_call(
                    "plan_indoor_route",
                    {"start": "entrance_east", "destination": "THEATRE_A"},
                    "c2",
                )
            ],
        ),
        llm.LlmResult(ok=True, text="Take the lift up to the first floor."),
    )
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "chat", fake)
    # The real classifier's verdict on this message:
    monkeypatch.setattr(llm, "classify", lambda system, text: {"category": "emergency"})

    body = call(
        "I'm at the East entrance and I hurt my ankle. Take me to Lecture Theatre A.",
        {**PLAIN, **AT_BUILDING},
        session_id="s-injury",
    )

    assert body["phase"] == "indoor", body
    assert body["ui"]["escalation"] is None
    assert body["ui"]["indoor_route"]["accessible"] is True
    rules = [event["rule"] for event in body["guardrails"]]
    assert "emergency_downgraded" in rules, rules
    assert "no_stairs_inferred" in rules


def test_the_classifier_can_still_escalate_a_genuine_emergency(monkeypatch):
    """The counterweight: downgrading must not disarm F9."""
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "classify", lambda system, text: {"category": "emergency"})
    monkeypatch.setattr(llm, "chat", ScriptedLLM(llm.LlmResult(ok=True, text="ok")))

    body = call("there is smoke coming from the lift", {**PLAIN, **AT_BUILDING}, "s-real-emg")
    assert body["phase"] == "escalated", body
    assert body["ui"]["escalation"]["needs_confirmation"] is True


def test_asking_for_a_person_still_escalates():
    """The counterpart to the above: real requests for help must still get through."""
    body = call("I need help, can I talk to someone?", PLAIN, session_id="s-help")
    assert body["phase"] == "escalated"
    assert body["ui"]["escalation"]["needs_confirmation"] is True


def test_timetable_endpoint_returns_the_week(scripted):
    body = client.get("/api/timetable?demo_time=2026-11-09T09:20:00%2B00:00").json()
    assert len(body["classes"]) >= 3
    assert body["next_class"]["room_id"] == "THEATRE_A"
    starts = [item["start"] for item in body["classes"]]
    assert starts == sorted(starts)
