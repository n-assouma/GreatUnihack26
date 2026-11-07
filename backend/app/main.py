"""Find My Way: FastAPI app (Agent 2).

Run from the `backend/` folder so `import indoor` works:
    uvicorn app.main:app --reload --port 8000

Endpoints follow docs/CONTRACTS.md §3 exactly.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from . import indoor_api, llm, orchestrator, timetable, tools, transit, tts
from .models import (
    GEOFENCE_RADIUS_M,
    ChatRequest,
    ChatResponse,
    ChatUI,
    ClassInfo,
    Escalation,
    EscalationConfirmRequest,
    GuardrailEvent,
    HealthResponse,
    IndoorRoute,
    OutdoorRoute,
    SessionDebug,
    TickRequest,
    TtsRequest,
)
from .state import (
    SessionState,
    advance_phase,
    apply_context,
    distance_to_building,
    get_session,
    set_phase,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = REPO_ROOT / "data"  # Agent 3 owns this folder

load_dotenv(BACKEND_DIR / ".env")

app = FastAPI(title="Find My Way API", version="1.0.0")

# CORS: the Vite dev server (CONTRACTS §3)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Agent 3's indoor engine: router mount (CONTRACTS §3) ---
# try/except so the backend still boots if their module is mid-edit.
INDOOR_ROUTER_OK = False
try:
    from indoor.router import router as indoor_router

    app.include_router(indoor_router)
    INDOOR_ROUTER_OK = True
except Exception as exc:  # noqa: BLE001
    print(f"[main] indoor router not mounted ({type(exc).__name__}: {exc})")

# --- floor plan images (Agent 3's files, Agent 2 mounts) ---
FLOORPLAN_DIR = DATA_DIR / "floorplans"
FLOORPLAN_DIR.mkdir(parents=True, exist_ok=True)  # empty dir, so the mount cannot crash
app.mount("/static/floorplans", StaticFiles(directory=FLOORPLAN_DIR), name="floorplans")


def _checked(model: type[BaseModel], value: dict | None, label: str) -> BaseModel | None:
    """Validate one payload on its own, so a surprise in it (say an indoor route from a
    half-finished graph) is dropped with a log line instead of 500-ing the whole reply."""
    if value is None:
        return None
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        print(f"[main] dropped {label} from the response ({exc.error_count()} problems): {exc}")
        return None


def _ui(state: SessionState, open_panel: str | None = None) -> ChatUI:
    """Copy what the tools worked out into the response."""
    return ChatUI(
        next_class=_checked(ClassInfo, state.next_class, "next_class"),  # type: ignore[arg-type]
        outdoor_route=_checked(OutdoorRoute, state.outdoor_route, "outdoor_route"),  # type: ignore[arg-type]
        indoor_route=_checked(IndoorRoute, state.indoor_route, "indoor_route"),  # type: ignore[arg-type]
        escalation=_checked(Escalation, state.escalation, "escalation"),  # type: ignore[arg-type]
        open_panel=open_panel,  # type: ignore[arg-type]
    )


def _response(
    state: SessionState,
    reply: str | None,
    events: list[GuardrailEvent] | None = None,
    open_panel: str | None = None,
) -> ChatResponse:
    return ChatResponse(
        reply=reply,
        agent=state.active_agent,
        phase=state.phase,
        ui=_ui(state, open_panel),
        guardrails=events or [],
    )


def _warnings() -> list[str]:
    """Things that look configured but cannot work. Reporting a credential as
    working when it provably is not defeats the point of a health endpoint."""
    notes: list[str] = []

    missing = llm.missing_dependencies()
    if missing:
        notes.append(
            f"litellm needs {', '.join(missing)} at call time and it is not installed, so "
            f"every LLM call will fail and replies will come from templates. "
            f"Fix: pip install -r requirements.txt"
        )
    if llm.available() and llm.status() == "degraded" and not missing:
        notes.append("An LLM call has failed this run; replies are falling back to templates.")
    if not llm.available():
        notes.append("No LLM configured (MOCK_LLM=1 or no API key): replies come from templates.")

    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if key and not key.startswith(tts.KEY_PREFIX):
        notes.append(
            "ELEVENLABS_API_KEY does not start with 'sk_', so it is an API key ID rather than "
            "an API key and voice cannot work. Create or rotate a key in ElevenLabs."
        )
    if not os.getenv("GOOGLE_MAPS_API_KEY"):
        notes.append("No GOOGLE_MAPS_API_KEY: the bus leg will be declined rather than invented.")
    if not INDOOR_ROUTER_OK:
        notes.append("The indoor engine did not load; indoor guidance is unavailable.")
    return notes


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """What is real and what is mocked right now (PLAN §5)."""
    return HealthResponse(
        ok=True,
        mocks={
            "llm": llm.status(),
            "routes": transit.status(),
            "tts": tts.status(),
            "indoor": indoor_api.status() if INDOOR_ROUTER_OK else "mock",
        },
        warnings=_warnings(),
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    state = get_session(req.session_id)
    apply_context(state, req.context)
    turn = orchestrator.run_turn(state, req.message)
    return _response(state, turn.reply, turn.events, turn.open_panel)


@app.post("/api/tick", response_model=ChatResponse)
def tick(req: TickRequest) -> ChatResponse:
    """Polled every 15 s. Templates only, no LLM: the app speaks up on its own for a
    mode switch, a class reminder or a change in how urgent the journey is (F13)."""
    state = get_session(req.session_id)
    apply_context(state, req.context)

    if state.next_class is None:
        tools.get_next_class(state)

    # 1. Dynamic mode-switching: walking into the geofence changes mode with no
    #    button press and no model involved (F12).
    announcement = advance_phase(state)
    if announcement:
        return _response(state, announcement, open_panel="floorplan")

    next_class = state.next_class
    minutes = timetable.minutes_until(next_class, state.now())

    # 2. Class reminder, once per class.
    if next_class and minutes is not None and 0 <= minutes <= 45:
        identifier = timetable.class_id(next_class)
        if identifier and identifier not in state.reminded_class_ids:
            state.reminded_class_ids.add(identifier)
            where = next_class["room_label"]
            reply = (
                f"Your next class, {next_class['title']}, starts in {round(minutes)} minutes "
                f"in {where}."
            )
            if state.phase == "idle":
                set_phase(state, "outdoor")
            state.remember("assistant", reply)
            return _response(state, reply)

    # 3. The journey became urgent since we last said anything.
    route = state.outdoor_route
    if route and route.get("status") in ("hurry", "late") and state.warned_status != route["status"]:
        state.warned_status = route["status"]
        reply = (
            "You need to leave now to make it on time."
            if route["status"] == "hurry"
            else "You're running late for this one. Shall I find the quickest way in?"
        )
        state.remember("assistant", reply)
        return _response(state, reply, open_panel="map")

    return _response(state, None)


@app.post("/api/escalation/confirm", response_model=ChatResponse)
def escalation_confirm(req: EscalationConfirmRequest) -> ChatResponse:
    """The user answered "Shall I contact reception?" (F9)."""
    state = get_session(req.session_id)
    escalation = state.escalation

    if not req.confirm:
        state.escalation = None
        set_phase(state, state.previous_phase if state.previous_phase != "escalated" else "indoor")
        reply = "No problem. Let's carry on — tell me where you are and I'll guide you."
        state.remember("assistant", reply)
        return _response(state, reply)

    if escalation is None:
        reply = "There's nothing waiting to be sent. Tell me what's wrong and I'll help."
        return _response(state, reply)

    entry = {
        "session_id": state.session_id,
        "at": state.now().isoformat(),
        "reason": escalation.get("reason"),
        "last_known": escalation.get("last_known"),
        "next_class": (state.next_class or {}).get("room_label"),
    }
    state.escalation_log.append(entry)
    print(f"[escalation] {entry}")  # the "staff view" in the server log

    escalation["needs_confirmation"] = False
    # D8: we log the request on our own server and say exactly that. No invented numbers.
    escalation["message"] = (
        "I've logged a request for help with your last position. Please go to the reception "
        "desk on the ground floor or ask a member of staff."
    )
    state.escalation = escalation
    state.remember("assistant", escalation["message"])
    return _response(state, escalation["message"])


@app.get("/api/timetable")
def get_timetable(demo_time: str | None = None) -> dict:
    """The week's classes, for the Calendar page (A1's request on the board).

    Additive: no existing response shape changes. Pending a human adding the row to
    CONTRACTS §3.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    if demo_time:
        try:
            parsed = datetime.fromisoformat(demo_time)
            now = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    classes = timetable.week(now)
    return {
        "classes": classes,
        "next_class": timetable.next_class(now),
        "now": now.isoformat(),
    }


@app.get("/api/escalations")
def escalations() -> dict:
    """Tiny staff view for the judges: every help request logged this run."""
    from .state import _SESSIONS

    entries = [entry for session in _SESSIONS.values() for entry in session.escalation_log]
    return {"count": len(entries), "escalations": entries}


@app.get("/api/session/{session_id}", response_model=SessionDebug)
def get_session_debug(session_id: str) -> SessionDebug:
    state = get_session(session_id)
    return SessionDebug(
        phase=state.phase,
        agent=state.active_agent,
        next_class=state.next_class,  # type: ignore[arg-type]
        profile=state.profile,
        transport_pref=state.transport_pref,
        current_node=state.current_node,
        current_step=state.current_step,
        heading=state.heading,
        heading_source=state.heading_source,
        lost_count=state.lost_count,
    )


@app.get("/api/debug/geofence")
def geofence(session_id: str) -> dict:
    """Why did (or didn't) indoor mode switch? Saves guessing during the demo."""
    state = get_session(session_id)
    distance = distance_to_building(state)
    return {
        "location": state.last_location,
        "distance_m": round(distance, 1) if distance is not None else None,
        "radius_m": GEOFENCE_RADIUS_M,
        "inside": distance is not None and distance < GEOFENCE_RADIUS_M,
        "phase": state.phase,
    }


@app.post("/api/tts")
def speak(req: TtsRequest) -> Response:
    audio = tts.speak(req.text)
    if audio is None:
        # 503 is the frontend's cue to use the browser voice instead (F15).
        return Response(
            content=b"", status_code=503, headers={"X-Reason": "elevenlabs-unavailable"}
        )
    return Response(content=audio, media_type="audio/mpeg")
