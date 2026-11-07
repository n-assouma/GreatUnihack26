# CONTRACTS (shared, do not change without agreement + human edit)

All JSON uses `snake_case`. Times are ISO 8601 strings with timezone (`2026-11-07T09:00:00+00:00`).
Headings and bearings are degrees clockwise from north, 0 to 360.

## 1. Shared constants
```
BUILDING_ID        = "nancy_rothwell"
BUILDING_NAME      = "Nancy Rothwell Building"
BUILDING_LAT_LNG   = 53.469093, -2.234591  # building centre (Wikipedia / DBpedia)
GEOFENCE_RADIUS_M  = 120                  # large building: inside this → indoor mode
OUTSIDE_EAST_LAT_LNG = TBD              # human drops a pin just outside the East entrance (Rumford Street)
DEMO_HOME_LAT_LNG  = TBD                  # human picks one real student address (see PLAN §5 D3)
BACKEND_PORT       = 8000
FRONTEND_PORT      = 5173                  # Vite proxies /api and /static → :8000
```

### Demo rooms (Agent 3 guarantees these exist in the graph; Agent 2's timetable uses them)
| room id | floor | note |
|---|---|---|
| `THEATRE_A` | 1 | **Main demo room**: Lecture Theatre A, first floor. Main demo start: `entrance_east` |
| `3A.041` | 3 | Second demo room, visible on the public floor plan PDF |

Agent 3 confirms both rooms are on the plan at M0 and posts the result on the board. If one is not, the humans pick another room from the plan and edit this table.

### Entrance node ids (Agent 3 guarantees)
`entrance_east` (Rumford Street, near Core 3) · `entrance_south` (Booth Street East) · `entrance_north`

## 2. Shared types
```ts
type Phase = "idle" | "outdoor" | "indoor" | "arrived" | "escalated";
type AgentName = "coordinator" | "journey" | "indoor";

interface Accessibility {
  no_stairs: boolean;          // injury / wheelchair: never route via stairs
  visual_impairment: boolean;  // more verbal detail, auto voice
}

interface ClientContext {
  lat?: number; lng?: number;          // browser geolocation or demo preset
  heading?: number | null;             // compass, null if unavailable
  demo_time?: string | null;           // overrides "now" when set
  accessibility: Accessibility;
  transport_pref?: "walk" | "run" | "bus" | null;
  current_step?: number | null;        // index of the indoor step the user is on
}

interface ClassInfo {
  title: string; start: string; end: string;
  building_id: string; room_id: string; room_label: string;
}

interface OutdoorLeg {
  mode: "WALK" | "BUS" | "TRAM" | "TRAIN";
  instruction: string;
  duration_min: number;
  line?: string | null;               // e.g. "142"
  from_stop?: string | null; to_stop?: string | null;
  depart_at?: string | null; arrive_at?: string | null;
}

interface OutdoorRoute {
  mode: "walk" | "run" | "bus";
  leave_at: string; arrive_at: string; class_start: string;
  status: "on_time" | "hurry" | "late";   // hurry = less than 5 min spare
  minutes_spare: number;                   // negative when late
  summary: string;                         // "Bus 142, 18 min, arrive 08:52"
  legs: OutdoorLeg[];
  polyline: string;                        // Google encoded polyline
}

interface IndoorStep {
  index: number;
  instruction: string;        // "Walk 20 m to the Core 3 lifts"
  floor: number;
  from_node: string; to_node: string;
  distance_m: number;
  bearing_deg: number | null; // absolute direction of this step, null for lift/stairs
  turn: "start" | "straight" | "slight_left" | "slight_right" | "left" | "right"
      | "turn_around" | "lift" | "stairs" | "arrive";   // relative to previous step
  via?: "lift" | "stairs" | null;
  target_floor?: number | null;   // for lift/stairs steps
}

interface FloorSegment {
  floor: number;
  image_url: string;                 // "/static/floorplans/floor_0.png"
  points: [number, number][];        // pixel coords on that image, in walking order
  step_indices: number[];            // which steps belong to this segment
}

interface IndoorRoute {
  start_node: string; destination_id: string;
  accessible: boolean; total_distance_m: number;
  steps: IndoorStep[];
  segments: FloorSegment[];
}

interface Escalation {
  reason: "lost" | "injured" | "user_request" | "guardrail";
  needs_confirmation: boolean;       // true = ask user "Shall I contact reception?" first
  message: string;
  contacts: { name: string; phone?: string | null; note?: string | null }[];
  last_known: { lat?: number | null; lng?: number | null; node_id?: string | null; floor?: number | null };
}

interface GuardrailEvent {
  stage: "input" | "tool" | "output";
  rule: string;                      // e.g. "off_topic", "no_stairs_enforced", "unknown_room"
  action: "blocked" | "modified" | "escalated";
  message: string;
}

interface ChatResponse {
  reply: string | null;              // text to show and speak (null = nothing new)
  agent: AgentName;
  phase: Phase;
  ui: {
    next_class?: ClassInfo | null;
    outdoor_route?: OutdoorRoute | null;
    indoor_route?: IndoorRoute | null;
    escalation?: Escalation | null;
    open_panel?: "map" | "floorplan" | null;   // suggestion only, user can override
  };
  guardrails: GuardrailEvent[];      // empty list if none fired
}
```

## 3. HTTP API (FastAPI, port 8000)
| Method + path | Owner | Request | Response |
|---|---|---|---|
| `POST /api/chat` | Agent 2 | `{session_id: string, message: string, context: ClientContext}` | `ChatResponse` |
| `POST /api/tick` | Agent 2 | `{session_id: string, context: ClientContext}` | `ChatResponse` (reply null unless reminder / late warning / mode switch) |
| `POST /api/escalation/confirm` | Agent 2 | `{session_id: string, confirm: boolean}` | `ChatResponse` |
| `GET /api/session/{session_id}` | Agent 2 | | `{phase, agent, next_class, profile}` (debug) |
| `POST /api/tts` | Agent 2 | `{text: string}` | `audio/mpeg` bytes (503 if no key → frontend uses browser voice) |
| `GET /api/health` | Agent 2 | | `{ok: true, mocks: {llm, routes, tts, indoor}}` |
| `GET /api/indoor/building` | Agent 3 | | `BuildingSummary` |
| `POST /api/indoor/route` | Agent 3 | `{start: string, destination: string, accessible: boolean, heading?: number}` | `IndoorRoute` (404 unknown node) |
| `POST /api/indoor/locate` | Agent 3 | `{text: string}` | `LocateResult` |
| `GET /static/floorplans/*` | Agent 3 files, Agent 2 mounts | | PNG images from `data/floorplans/` |

- Frontend generates `session_id` once (uuid in localStorage).
- `/api/tick` is polled by the frontend every 15 s and whenever location or demo preset changes.
- Agent 2 mounts Agent 3's router with exactly: `from indoor.router import router as indoor_router; app.include_router(indoor_router)`
  and static files with `app.mount("/static/floorplans", StaticFiles(directory=DATA_DIR/"floorplans"))`.
- Backend runs from `backend/` folder: `uvicorn app.main:app --reload --port 8000` (so `import indoor` works).
- CORS: allow `http://localhost:5173`.

```ts
interface BuildingSummary {
  building_id: string; name: string; north_offset_deg: number;
  floors: { floor: number; label: string; image_url: string; width: number; height: number; pixels_per_metre: number }[];
  entrances: { id: string; label: string; floor: number }[];
  rooms: { id: string; label: string; floor: number }[];
}
interface LocateResult {
  node_id: string | null;            // best match, null if not confident
  confidence: number;                // 0 to 1
  candidates: { node_id: string; label: string; floor: number }[];
}
```

## 4. Python interface (Agent 2 imports, Agent 3 implements) `backend/indoor/api.py`
```python
def get_building_summary() -> dict: ...                       # BuildingSummary
def heading_towards(from_node: str, text: str) -> float | None: ...
    # "I'm facing the lifts" → bearing (deg) from from_node to the landmark named in text, None if unclear
def locate(text: str) -> dict: ...                            # LocateResult
def room_exists(room_id: str) -> bool: ...
def node_exists(node_id: str) -> bool: ...
def get_indoor_route(start: str, destination: str,
                     accessible: bool, heading: float | None = None) -> dict: ...   # IndoorRoute
# Raises indoor.api.UnknownNodeError for bad ids, indoor.api.NoRouteError if no path.
# heading=None and start is an entrance → use that entrance's facing_deg (direction you face when walking in).
# heading=None otherwise → first step turn is "start" and instructions use landmarks only.
```
Agent 2 must call `get_indoor_route(..., accessible=True)` whenever `context.accessibility.no_stairs` is true,
whatever the LLM asked for.

## 5. Building JSON schema `data/building/nancy_rothwell.json` (Agent 3 owns)
```json
{
  "building_id": "nancy_rothwell",
  "name": "Nancy Rothwell Building",
  "north_offset_deg": 0,
  "floors": [{"floor": 0, "label": "Ground", "image": "floor_0.png", "width": 1200, "height": 800, "pixels_per_metre": 8.0}],
  "nodes": [{"id": "entrance_east", "floor": 0, "x": 1120, "y": 410, "type": "entrance", "facing_deg": 270,
             "label": "East entrance (Rumford Street)", "aliases": ["east door", "rumford street entrance"]}],
  "edges": [{"from": "entrance_east", "to": "f0_core3_lobby", "type": "corridor", "accessible": true, "keycard": false}]
}
```
- node `type`: `entrance | corridor | junction | lift | stairs | room | toilet | landmark`
- `facing_deg` (entrances only): compass bearing a person faces right after walking in through that entrance.
- edge `type`: `corridor | door | ramp | stairs | lift`. Stairs edges: `accessible: false`.
- Node id convention: `f{floor}_{name}` (e.g. `f3_core4_lift`), except rooms (room code, e.g. `3A.041`) and entrances.

## 6. Dependencies (Agent 2 puts all of these in `backend/requirements.txt` at M0)
```
fastapi uvicorn[standard] pydantic python-dotenv httpx litellm
icalendar networkx Pillow pytest
```
Frontend (Agent 1): `react react-dom @vis.gl/react-google-maps uuid` + Vite TS template.

## 7. Environment variables
`backend/.env`: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` (optional), `LLM_MODEL=anthropic/claude-sonnet-5`,
`GUARD_MODEL=anthropic/claude-haiku-4-5`, `GOOGLE_MAPS_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`,
`MOCK_LLM=0|1` (D6 fallback), `ROUTE_REPLAY=0|1` (D5 safety net)
`frontend/.env`: `VITE_GOOGLE_MAPS_API_KEY`, `VITE_USE_MOCKS=0|1`

> Model ids corrected on Amir's instruction (was `claude-sonnet-5-5` / `claude-haiku-5-5`, neither of
> which exists). litellm does **not** validate model ids — it reports the invalid ones as real, so the
> failure would have been a 404 on the first chat message during the demo. Copy from
> `backend/.env.example`, which carries the same values. Variable names are unchanged.
