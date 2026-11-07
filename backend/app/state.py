"""Session state, the phase machine and geo helpers.

State lives in a plain in-memory dict keyed by session_id. The frontend keeps the
id in localStorage, so reloading the page keeps the conversation (F3).

The phase machine is deliberately **deterministic code, not a prompt**: it runs
before the LLM on every request, so dynamic mode-switching (F12) cannot be talked
out of happening by the model or by the user.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .models import (
    BUILDING_LAT,
    BUILDING_LNG,
    GEOFENCE_RADIUS_M,
    Accessibility,
    AgentName,
    ClientContext,
    Phase,
    TransportMode,
)

HISTORY_LIMIT = 20

# Phase -> the agent that owns it
AGENT_FOR_PHASE: dict[str, AgentName] = {
    "idle": "coordinator",
    "outdoor": "journey",
    "indoor": "indoor",
    "arrived": "coordinator",
    "escalated": "coordinator",
}


@dataclass
class SessionState:
    session_id: str
    phase: Phase = "idle"
    previous_phase: Phase = "idle"
    active_agent: AgentName = "coordinator"

    # profile
    profile: Accessibility = field(default_factory=Accessibility)
    # The Settings toggle, resent on every request by the frontend.
    transport_pref: TransportMode | None = None
    # A mode the user named in a message. This outranks the Settings value, because
    # saying "I'll walk" has to beat a stale "Run" left in someone's Settings — but
    # it is cleared the moment Settings changes, so changing Settings still works.
    spoken_transport: TransportMode | None = None
    _seen_context_pref: TransportMode | None = None
    _seen_any_context_pref: bool = False
    # Set when the user *says* they are injured ("I hurt my ankle"). Kept apart from
    # `profile`, which is overwritten from the client context on every request.
    inferred_no_stairs: bool = False

    # where the user is
    last_location: tuple[float, float] | None = None
    heading: float | None = None
    heading_source: str | None = None  # "entrance" | "spoken" | "compass" | None
    current_node: str | None = None
    current_floor: int | None = None
    current_step: int | None = None

    # what the tools worked out
    next_class: dict | None = None
    outdoor_route: dict | None = None
    indoor_route: dict | None = None

    # conversation + safety
    history: list[dict] = field(default_factory=list)  # [{"role","content"}], text turns only
    # lost_count counts every "we don't know where they are" signal, including a
    # location we could not pin down. said_lost_count counts only the user actually
    # telling us they are lost — escalation needs that, because failing to resolve
    # "by the lifts" twice is ambiguity, not distress.
    lost_count: int = 0
    said_lost_count: int = 0
    escalation: dict | None = None
    escalation_log: list[dict] = field(default_factory=list)
    reminded_class_ids: set[str] = field(default_factory=set)
    warned_status: str | None = None

    # demo mode
    demo_time: str | None = None

    def remember(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        if len(self.history) > HISTORY_LIMIT:
            del self.history[: len(self.history) - HISTORY_LIMIT]

    def now(self) -> datetime:
        """"Now" is the demo clock when set, otherwise the real clock (D2)."""
        if self.demo_time:
            try:
                parsed = datetime.fromisoformat(self.demo_time)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    @property
    def demo_mode(self) -> bool:
        return self.demo_time is not None

    @property
    def transport(self) -> TransportMode | None:
        """How they are travelling: what they last said, else the Settings value."""
        return self.spoken_transport or self.transport_pref

    @property
    def no_stairs(self) -> bool:
        """The single source of truth for accessible routing (F5). The toggle in the
        UI and anything the user told us both count."""
        return self.profile.no_stairs or self.inferred_no_stairs

    @property
    def visual_impairment(self) -> bool:
        return self.profile.visual_impairment


_SESSIONS: dict[str, SessionState] = {}


def get_session(session_id: str) -> SessionState:
    state = _SESSIONS.get(session_id)
    if state is None:
        state = SessionState(session_id=session_id)
        _SESSIONS[session_id] = state
    return state


def reset_sessions() -> None:
    """Tests only."""
    _SESSIONS.clear()


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance in metres between two lat/lng points."""
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_phi = p2 - p1
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def distance_to_building(state: SessionState) -> float | None:
    if state.last_location is None:
        return None
    lat, lng = state.last_location
    return haversine_m(lat, lng, BUILDING_LAT, BUILDING_LNG)


def apply_context(state: SessionState, ctx: ClientContext) -> None:
    """Every request carries the live client context; fold it into the session."""
    state.profile = ctx.accessibility
    state.demo_time = ctx.demo_time

    # A *changed* Settings value is a deliberate new choice, so it clears anything the
    # user said earlier. An unchanged one is just the frontend resending the same
    # toggle every request, and must not undo what they said a moment ago.
    if not state._seen_any_context_pref or ctx.transport_pref != state._seen_context_pref:
        if state._seen_any_context_pref:
            state.spoken_transport = None
        state._seen_any_context_pref = True
        state._seen_context_pref = ctx.transport_pref
    if ctx.transport_pref is not None:
        state.transport_pref = ctx.transport_pref
    if ctx.lat is not None and ctx.lng is not None:
        state.last_location = (ctx.lat, ctx.lng)
    if ctx.heading is not None:
        # A real compass reading always wins over a spoken or entrance-derived one.
        state.heading = ctx.heading
        state.heading_source = "compass"
    if ctx.current_step is not None:
        state.current_step = ctx.current_step


def set_phase(state: SessionState, phase: Phase) -> None:
    if phase == state.phase:
        return
    state.previous_phase = state.phase
    state.phase = phase
    state.active_agent = AGENT_FOR_PHASE.get(phase, "coordinator")


# Words that mean "I am at the building now" / "I am at the room now".
_ARRIVED_WORDS = ("i've arrived", "i have arrived", "i'm here", "im here", "i'm there",
                  "im there", "arrived", "i'm at the building", "i'm outside")
_JOURNEY_WORDS = ("get to", "getting to", "how do i get", "travel", "bus", "walk", "run",
                  "leave", "late", "on time", "journey", "next class", "my class")

# Phrases that introduce where someone is standing. One of these plus a place the
# indoor engine actually recognises means they are telling us they are at the building.
_POSITION_CUES = ("i'm at", "im at", "i am at", "i'm by", "im by", "i'm near", "im near",
                  "i am near", "i'm next to", "i'm outside", "im outside", "i'm standing",
                  "near the", "next to the", "by the", "at the", "outside the")


# Whole-word so "run" does not match "running late" and "bus" does not match "busy".
_TRANSPORT_WORDS: tuple[tuple[str, str], ...] = (
    ("bus", r"\bbus(?:es)?\b"),
    # "running late" and "run out of time" mean delayed, not "I'll run there".
    ("run", r"\brun(?:ning)?\b(?!\s+(?:late|out|behind))|\bjog(?:ging)?\b"),
    ("walk", r"\bwalk(?:ing)?\b|\bon foot\b"),
)


def transport_in_message(message: str) -> str | None:
    """The travel mode the user just named, if any."""
    text = message.lower()
    for mode, pattern in _TRANSPORT_WORDS:
        if re.search(pattern, text):
            return mode
    return None


def _states_a_position(message: str) -> bool:
    """True when the user says where they are and the building knows that place.

    Asking the indoor engine beats a keyword list: it covers "I'm at the East
    entrance", "near the Core 3 lifts" and "by the main door" without us having to
    enumerate every phrasing, and it cannot match a place the building doesn't have.
    """
    text = message.lower()
    if not any(cue in text for cue in _POSITION_CUES):
        return False

    from . import indoor_api

    found = indoor_api.locate(message)
    try:
        confidence = float(found.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    return bool(found.get("node_id")) and confidence >= 0.5


def advance_phase(state: SessionState, message: str = "") -> str | None:
    """Deterministic transitions. Returns a template announcement when the app
    itself should say something about the change (mode switch), else None."""
    text = message.lower()
    # Two different signals, and conflating them breaks the demo: "I'm at the East
    # entrance" means they have reached the *building* (start guiding them), while
    # "I'm here" on the last step means they have reached the *room* (stop guiding).
    states_position = _states_a_position(message)
    said_arrived = any(word in text for word in _ARRIVED_WORDS)
    distance = distance_to_building(state)
    inside = distance is not None and distance < GEOFENCE_RADIUS_M

    # Escalation owns the session until it is resolved or declined — except when the
    # student plainly moves on instead of answering the card ("I'm at the East
    # entrance"). Treating that as a decline stops one escalation from stranding the
    # rest of the conversation, which is how a single wrong escalation cascaded into
    # every later step failing.
    if state.phase == "escalated":
        awaiting = (state.escalation or {}).get("needs_confirmation", False)
        if awaiting and states_position:
            state.escalation = None
            set_phase(state, "indoor")
        return None

    # -> indoor: at the building, or the user says where in it they are (F12)
    if state.phase in ("idle", "outdoor", "arrived") and (inside or said_arrived or states_position):
        set_phase(state, "indoor")
        if state.current_node is None:
            return (
                "You're at the Nancy Rothwell Building. Which entrance are you at?"
            )
        return None

    # indoor -> arrived: on the last step, or they say they are there — but saying
    # where they are standing is not the same as having got there.
    if state.phase == "indoor":
        steps = (state.indoor_route or {}).get("steps") or []
        on_last_step = bool(
            steps and state.current_step is not None and state.current_step >= len(steps) - 1
        )
        if on_last_step or (said_arrived and not states_position):
            set_phase(state, "arrived")
        return None

    # idle -> outdoor: asking about the journey, or the class starts within the hour
    if state.phase == "idle":
        soon = False
        start = (state.next_class or {}).get("start")
        if start:
            try:
                minutes = (datetime.fromisoformat(start) - state.now()).total_seconds() / 60
                soon = 0 <= minutes <= 60
            except ValueError:
                soon = False
        if soon or any(word in text for word in _JOURNEY_WORDS):
            set_phase(state, "outdoor")

    return None
