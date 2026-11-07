# Agent 2: AI agents backend (multi-agent, guardrails, journey, voice)

**You own:** `backend/app/**`, `backend/requirements.txt`, `backend/.env.example`, root `README.md`, root `.gitignore`.
You **import** Agent 3's `indoor.api` and **mount** `indoor.router`; you never edit `backend/indoor/` or `data/`.

> **Before you start:** follow `AGENTS.md` (board posts as `[<human>'s Claude A2]`, tag owners by GitHub login,
> branch + PR per issue, stage only your own files). Only fake what PLAN §5 lists. Never idle (PLAN top).
> Your work is done when it meets its rows in PLAN §3 (F1, F2, F3, F8, F9, F10, F11, F12, F13, F15) and the global definition of done.

## Goal
The FastAPI server and the multi-agent brain: Coordinator, Journey and Indoor agents with handoffs, session state,
guardrail pipeline, human-in-the-loop escalation, timetable, Google transit routes and ElevenLabs TTS.
Reply judges look at this part most, so make every feature **visible** in `ChatResponse` (agent name, guardrail events).

## Order of work
1. **M0 (by 13:50):** `requirements.txt` (CONTRACTS §6), `.env.example`, `.gitignore` (`.env`, `node_modules`,
   `__pycache__`, `.venv`, `.board`), `README.md` (run steps). `app/main.py` with every endpoint from CONTRACTS
   returning a fixed contract-shaped response (D7), CORS for :5173, `include_router(indoor_router)` and the static
   mount exactly as in CONTRACTS (try/except around the import until Agent 3's stub lands). Run from `backend/`:
   `uvicorn app.main:app --reload --port 8000`. Post "backend stub up" on the board.
2. **M1 (by 14:30), P0:** state + phase machine, LLM client, orchestrator with the 3 agents and handoffs, tools,
   guardrails, escalation, timetable (D1).
3. **M2 (by 15:30):** Google Routes (bus/walk/run), `/api/tick` (reminders, hurry, geofence switch), facing
   direction from words, `/api/tts` ElevenLabs.

## Files
```
backend/app/
  main.py          # FastAPI app + endpoints, builds ChatResponse from state
  models.py        # Pydantic models = CONTRACTS types
  state.py         # SessionState store (in-memory dict) + phase machine + haversine
  llm.py           # LiteLLM wrapper: chat(model, system, messages, tools) with timeout + D6 fallback
  orchestrator.py  # run_turn(): guardrails → active agent → tool loop → handoffs → output guardrail
  agents.py        # the 3 agent definitions (prompt, tools, allowed handoffs)
  tools.py         # tool schemas (OpenAI function format) + Python implementations
  guardrails.py    # input / tool / output guardrails, each returns GuardrailEvent(s)
  timetable.py     # load data/timetable.json, next class for "now" (demo_time aware)
  transit.py       # Google Routes client (+ D5 record/replay)
  tts.py           # ElevenLabs client
  data/timetable.json, data/route_recorded.json
```

## LLM (Anthropic via LiteLLM)
- `litellm.completion(model=os.environ["LLM_MODEL"], messages=[{"role":"system",...}, ...], tools=[...], timeout=20)`.
  Default `LLM_MODEL=anthropic/claude-sonnet-5-5`; guardrail classifier `GUARD_MODEL=anthropic/claude-haiku-5-5`.
  Gemini later = change `LLM_MODEL` to a `gemini/...` model, no code change.
- Tool calls come back as `choices[0].message.tool_calls` (OpenAI format). Max 6 tool rounds per turn.
- Any exception or timeout → D6 template reply built from tool results, and `/api/health` reports `llm: "mock"`.

## Session state (`state.py`)
`SessionState`: `session_id, phase, active_agent, previous_phase, profile (Accessibility + transport_pref),
next_class, last_location, heading, heading_source ("entrance" | "spoken" | "compass" | None), current_node,
current_step, outdoor_route, indoor_route, lost_count, escalation, reminded_class_ids, warned_status,
history (last 20 messages), escalation_log`. Update profile, location, heading, current_step from every request's
`context`. In-memory dict keyed by `session_id` (frontend keeps the id in localStorage, so reload keeps the chat).

## Phase machine (dynamic mode-switching, deterministic code, runs before the LLM)
- `idle` → `outdoor`: user asks about getting to class, or the next class starts within 60 min.
- `outdoor` → `indoor`: haversine(location, BUILDING_LAT_LNG) < GEOFENCE_RADIUS_M, or the user says they've arrived.
  Template reply: "You're at the Nancy Rothwell Building. Which entrance are you at?" + `ui.open_panel = "floorplan"`.
- `indoor` → `arrived`: `current_step` is the last step, or the user says they're there.
- any → `escalated` on escalation; back to `previous_phase` when resolved or declined.
- Phase sets `active_agent`: outdoor → journey, indoor → indoor, otherwise coordinator.

## Orchestrator (`orchestrator.py`) and agents (`agents.py`)
```
run_turn(state, message):
  events = input_guardrail(message, state)            # may block or escalate → return early
  agent = AGENTS[state.active_agent]
  loop (max 6):
     reply = llm.chat(agent.model, agent.system(state), state.history, agent.tools + handoff tools)
     for each tool_call:
        if it is transfer_to_<agent>: state.active_agent = target; record handoff; restart loop with new agent
        else: args = tool_guardrail(name, args, state, events); result = TOOLS[name](state, **args)
     if no tool_calls: text = output_guardrail(reply, state, events); return ChatResponse
```
- **Coordinator**: short and friendly. Knows the next class, answers general campus questions, hands off.
  Tools: `get_next_class`, `escalate_to_human`, `transfer_to_journey`, `transfer_to_indoor`.
- **Journey**: agrees transport mode (walk / run / bus), explains route and timing.
  Tools: `get_next_class`, `plan_outdoor_route(mode)`, `escalate_to_human`, `transfer_to_coordinator`.
- **Indoor**: works out where the user is and which way they face, then gives **one step at a time**, says the floor
  and the lift. Tools: `locate_user(text)`, `set_facing(text)`, `plan_indoor_route(start, destination)`,
  `escalate_to_human`, `transfer_to_coordinator`.
- `agent.system(state)` = role prompt + a short state summary (phase, next class, room, accessibility, current node,
  current step). Rules in every prompt: plain English, 1 to 3 sentences (it is spoken), only describe what tools
  returned, never invent rooms, buses or directions; for `visual_impairment` describe landmarks and distances.
- Tools store results in state (`next_class`, `outdoor_route`, `indoor_route`); `main.py` copies them into `ChatResponse.ui`.
  `ChatResponse.agent` = agent that wrote the final reply.

## Tools (`tools.py`)
- `get_next_class()` → `timetable.py` (D1: from Nael's real timetable screenshot, typed into `data/timetable.json`;
  in demo mode the demo class is Lecture Theatre A, room id `THEATRE_A`). "Now" = `context.demo_time` or real time.
  Ask your human for the screenshot right away; until it arrives use the D7 stub class.
- `plan_outdoor_route(mode)` → `transit.py`: `POST https://routes.googleapis.com/directions/v2:computeRoutes`,
  headers `X-Goog-Api-Key`, `X-Goog-FieldMask: routes.duration,routes.polyline.encodedPolyline,routes.legs.steps.travelMode,routes.legs.steps.staticDuration,routes.legs.steps.transitDetails,routes.legs.steps.navigationInstruction`,
  body `origin/destination` lat/lng, `travelMode: TRANSIT` (bus) or `WALK`, `arrivalTime` = class start minus 5 min.
  Run = walk duration × 0.6. Compute `leave_at`, `arrive_at`, `minutes_spare`, `status` (late < 0, hurry < 5).
  D5: save the first good response to `data/route_recorded.json`; replay it only if the live call fails.
- `locate_user(text)` → `indoor.api.locate`. `node_id` null → `lost_count += 1`, ask a clarifying question with the candidates.
  Found → `state.current_node`; if it is an entrance, `heading_source = "entrance"`.
- `set_facing(text)` → `indoor.api.heading_towards(current_node, text)` → `state.heading`, `heading_source = "spoken"`.
- `plan_indoor_route(start, destination)` → `indoor.api.get_indoor_route(start, destination, accessible, heading)`.
  `heading` = compass value if the frontend sent one, else the spoken heading, else None (Agent 3 uses the entrance direction).
- `escalate_to_human(reason)` → `Escalation` with `needs_confirmation: true`.

## Guardrail pipeline (`guardrails.py`): every event goes into `ChatResponse.guardrails`
1. **Input**: fast keyword check, then `GUARD_MODEL` classifier returning JSON `{category: on_topic | off_topic |
   unsafe | injection | emergency | lost}`. off_topic / unsafe / injection → polite refusal, `action: "blocked"`.
   emergency / lost → escalation path (`lost` increments `lost_count`, escalate at 2), `action: "escalated"`.
2. **Tool**: room / node must exist (`indoor.api.room_exists / node_exists`) else ask again (`rule: "unknown_room"`);
   force `accessible=True` when `no_stairs` (`rule: "no_stairs_enforced"`, `action: "modified"`); destination must be the
   class room unless the user named another room.
3. **Output**: no "stairs" in the reply when `no_stairs`; no room codes or bus lines that are not in tool results;
   max ~60 words. On failure, replace with a template built from tool data (`action: "modified"`).

## Human-in-the-loop escalation
- Triggers: `lost_count >= 2`, or emergency / hurt and cannot continue, or the user asks for a person.
- Reply "Shall I contact reception for you?" + `ui.escalation` (`needs_confirmation: true`), phase `escalated`.
- `POST /api/escalation/confirm {confirm: true}` → append to `escalation_log` (print it too), reply "I've logged a
  request for help with your last position. Please go to the reception desk on the ground floor or ask a member of staff.",
  `needs_confirmation: false`. `confirm: false` → back to the previous phase.
- Contacts (D8): `[{"name": "Nancy Rothwell reception", "phone": null, "note": "Ground floor reception desk"}]`.
  **Never invent phone numbers.** `last_known` = lat/lng, current_node, floor.
- Optional: `GET /api/escalations` returns `escalation_log` (a tiny "staff view" for the judges).

## `/api/tick` (real-time, no LLM)
Update state from context, then in order: geofence mode switch → class reminder (within 45 min, once per class) →
status change to hurry / late → else `reply: null`. Templates only.

## `/api/tts`
`POST https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}`, header `xi-api-key`,
body `{"text": ..., "model_id": "eleven_flash_v2_5"}` → return `audio/mpeg`. No key / error → HTTP 503.

## Tests (pytest, quick)
no_stairs user never gets a `stairs` step; geofence switches phase; off-topic input is blocked with an event;
`lost` twice produces an escalation; LLM failure still returns a valid ChatResponse.

## Ask your human for
`ANTHROPIC_API_KEY`, `GOOGLE_MAPS_API_KEY` (Routes API enabled), `ELEVENLABS_API_KEY` + voice id,
**the timetable screenshot**, the Home address and East entrance pin (send to Agent 1 too via the board).
