"""Find My Way: FastAPI app (Agent 2).

Run from the `backend/` folder so `import indoor` works:
    uvicorn app.main:app --reload --port 8000

Endpoints follow docs/CONTRACTS.md §3 exactly. M0 serves D7 stub data; M1 swaps
the stub calls for the multi-agent orchestrator.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .models import (
    ChatRequest,
    ChatResponse,
    ChatUI,
    EscalationConfirmRequest,
    HealthResponse,
    SessionDebug,
    TickRequest,
    TtsRequest,
)
from .stubs import STUB_CLASS, STUB_ESCALATION, stub_chat_response

BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = REPO_ROOT / "data"  # Agent 3 owns this folder

load_dotenv(BACKEND_DIR / ".env")

app = FastAPI(title="Find My Way API", version="0.1.0")

# CORS: the Vite dev server (CONTRACTS §3)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Agent 3's indoor engine: router mount (CONTRACTS §3) ---
# try/except so the backend still boots before their stub lands.
INDOOR_ROUTER_OK = False
try:
    from indoor.router import router as indoor_router

    app.include_router(indoor_router)
    INDOOR_ROUTER_OK = True
except Exception as exc:  # noqa: BLE001 - any import error must not stop the server
    print(f"[main] indoor router not mounted yet ({type(exc).__name__}: {exc})")

# --- floor plan images (Agent 3's files, Agent 2 mounts) ---
FLOORPLAN_DIR = DATA_DIR / "floorplans"
FLOORPLAN_DIR.mkdir(parents=True, exist_ok=True)  # empty dir, so the mount cannot crash
app.mount("/static/floorplans", StaticFiles(directory=FLOORPLAN_DIR), name="floorplans")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """What is real and what is mocked right now (PLAN §5)."""
    llm = "mock" if os.getenv("MOCK_LLM") == "1" or not os.getenv("ANTHROPIC_API_KEY") else "real"
    routes = "real" if os.getenv("GOOGLE_MAPS_API_KEY") else "mock"
    if os.getenv("ROUTE_REPLAY") == "1":
        routes = "replay"
    tts = "real" if os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_VOICE_ID") else "mock"
    indoor = "real" if INDOOR_ROUTER_OK else "mock"
    return HealthResponse(ok=True, mocks={"llm": llm, "routes": routes, "tts": tts, "indoor": indoor})


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    # M1: input guardrail -> phase machine -> orchestrator.run_turn -> output guardrail
    return stub_chat_response(req.message)


@app.post("/api/tick", response_model=ChatResponse)
def tick(req: TickRequest) -> ChatResponse:
    # M2: geofence mode switch -> class reminder -> hurry/late warning -> else reply None
    return ChatResponse(reply=None, agent="coordinator", phase="idle", ui=ChatUI(next_class=STUB_CLASS))


@app.post("/api/escalation/confirm", response_model=ChatResponse)
def escalation_confirm(req: EscalationConfirmRequest) -> ChatResponse:
    if not req.confirm:
        return ChatResponse(reply="No problem, let's carry on. (stub)", agent="coordinator", phase="indoor")
    confirmed = STUB_ESCALATION.model_copy(update={"needs_confirmation": False})
    return ChatResponse(
        reply=(
            "I've logged a request for help with your last position. Please go to the reception "
            "desk on the ground floor or ask a member of staff. (stub)"
        ),
        agent="coordinator",
        phase="escalated",
        ui=ChatUI(escalation=confirmed),
    )


@app.get("/api/session/{session_id}", response_model=SessionDebug)
def get_session(session_id: str) -> SessionDebug:
    from .models import Accessibility

    return SessionDebug(phase="idle", agent="coordinator", next_class=STUB_CLASS, profile=Accessibility())


@app.post("/api/tts")
def tts(req: TtsRequest) -> None:
    # M2: ElevenLabs eleven_flash_v2_5 -> audio/mpeg. 503 tells the frontend to use the browser voice.
    raise HTTPException(status_code=503, detail="TTS not configured yet; use the browser voice.")
