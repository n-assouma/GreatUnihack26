# Find My Way

GreatUniHack 2026 — Reply "AI on Campus" challenge.

An AI assistant that gets a University of Manchester student from home to the right classroom, on
time. It reads the next class from their timetable, agrees how they will travel (walk, run, bus) and
shows the route. When they reach the **Nancy Rothwell Building** it switches to indoor mode: the
student says where they are ("I'm at the East entrance") and the app guides them step by step on the
floor plan, using lifts instead of stairs for injured and wheelchair users. It works fully by voice,
so blind and visually impaired students can use it too. If the student is lost or hurt, it offers to
get a human involved.

Built by three agents working in parallel: see `AGENTS.md`, `docs/PLAN.md` and `docs/CONTRACTS.md`.

## Run it locally

Two terminals. Backend first.

### 1. Backend (port 8000)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in the keys you have
uvicorn app.main:app --reload --port 8000
```

Run it **from `backend/`** — that is what makes `import indoor` work.

Check it: <http://localhost:8000/api/health> → `{"ok":true,"mocks":{...}}`
Interactive API docs (every type from `docs/CONTRACTS.md`): <http://localhost:8000/docs>

### 2. Frontend (port 5173)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` and `/static` to port 8000, so the browser only
ever talks to 5173.

## Keys

All secrets live in `backend/.env` (gitignored, copy from `backend/.env.example`) and
`frontend/.env`. **Never commit a key.** The app degrades instead of crashing when one is missing:

| Missing key | What happens |
|---|---|
| `ANTHROPIC_API_KEY` | Replies come from fixed sentence templates filled with real tool results. `/api/health` reports `llm: "mock"` |
| `GOOGLE_MAPS_API_KEY` | No live bus route; a previously recorded real response is replayed if present |
| `ELEVENLABS_API_KEY` | `/api/tts` returns 503 and the browser's own voice speaks instead |

`/api/health` always tells you what is real and what is mocked.

## API

Full request and response types: `docs/CONTRACTS.md`. Live schema: `/docs`.

| Method + path | What it does |
|---|---|
| `POST /api/chat` | Send a message, get a reply plus the UI payload (next class, routes, escalation) |
| `POST /api/tick` | Polled every 15 s for reminders, "hurry" warnings and the indoor mode switch |
| `POST /api/escalation/confirm` | User answers "Shall I contact reception?" |
| `GET /api/session/{session_id}` | Session state, for debugging |
| `POST /api/tts` | Text to speech (503 → use the browser voice) |
| `GET /api/health` | What is real, what is mocked |
| `GET /api/indoor/building` | Building summary: floors, entrances, rooms |
| `POST /api/indoor/route` | Indoor route between two nodes |
| `POST /api/indoor/locate` | Turn "I'm at the east entrance" into a graph node |

## Tests

```bash
cd backend
.venv/bin/pytest
```

## Layout

```
backend/
  app/        # Agent 2: FastAPI, multi-agent orchestrator, guardrails, state, timetable, transit, TTS
  indoor/     # Agent 3: building graph, routing, turn-by-turn directions
frontend/     # Agent 1: React + Vite + TypeScript
data/         # Agent 3: building JSON + floor plan images (served at /static/floorplans)
docs/         # Plan and contracts (humans only)
```
