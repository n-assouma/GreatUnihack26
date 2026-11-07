# Find My Way: Implementation Plan

Every agent reads exactly 4 files: `AGENTS.md` (board rules) + `docs/PLAN.md` (this file) + `docs/CONTRACTS.md`
+ **only its own** agent file (`docs/agent-1-frontend.md`, `docs/agent-2-agents.md` or `docs/agent-3-indoor.md`).
Do **not** read the other agents' files or `context.md`. Kickoff prompts are in `docs/KICKOFF.md`.

**Work rule: never idle.** If you are blocked, keep going with the approved stub, post on the board, and pick the
next item in your file. Do not stop to wait for replies. Deadline: all P0 by **14:30**, everything by **15:30** at the latest.

---

## 1. Common goal
Win the **Reply "AI on Campus"** challenge at GreatUniHack 2026 with a working prototype: features finished by
**14:30 (target) / 15:30 (latest)**, submission before the 18:00 hard deadline.
The brief requires: an AI solution to a real university problem with **session state**, **guardrail pipelines** and
**real-time interaction**. Advanced teams add a **multi-agent system with specialised roles**, **dynamic mode-switching**
and **human-in-the-loop escalation**. Our demo must show all six clearly.

## 2. The app in brief
**Find My Way** gets a University of Manchester student from home to the right classroom, on time.
It knows their next class from their calendar, agrees how they will travel (walk, run, bus), shows the route and
tells them if they need to hurry. When they reach the **Nancy Rothwell Building**, it switches to indoor mode:
the student says where they are ("I'm at the East entrance"), and the app guides them step by step using the phone
compass ("turn left"), draws the route on the floor plan, and uses lifts instead of stairs for injured or wheelchair
users. It can be used fully by voice, so it also works for blind and visually impaired students. If the student is
lost or hurt, it offers to get a human (reception or security) involved.

Scope for today: web app (phone browser first), one building (Nancy Rothwell), floors Ground to 3.

## 3. Functionalities and definition of done
Priority: **P0** must be in the demo · **P1** should · **P2** if time. Owner in brackets.

| # | Functionality | Pri | Done when |
|---|---|---|---|
| F1 | **Next class from calendar** (A2) | P0 | The app shows the next class (title, time, room, building) for the current time or demo time, from the timetable file. |
| F2 | **Multi-agent conversation** (A2) | P0 | Coordinator, Journey and Indoor agents exist; a chat message reaches the right agent; the UI shows which agent answered; at least one handoff happens in the demo. |
| F3 | **Session state** (A2) | P0 | Profile, phase, next class, routes and position persist across messages in a session; reloading the page with the same session id keeps the conversation. |
| F4 | **Indoor route on the floor plan** (A3 data + routing, A1 drawing) | P0 | From each of the 3 entrances to the demo rooms (main demo: East entrance → Lecture Theatre A, first floor), the app returns a correct route (checked by a human against the plan) and draws it on the right floor image in a panel that opens on demand and does not cover the chat. Multi-floor routes switch floor at the lift. |
| F5 | **Accessible routing** (A3, enforced by A2) | P0 | With "no stairs" on, no route ever contains stairs (automated test + manual check); the app says to take the lift. |
| F6 | **Locate me from words** (A3, used by A2) | P0 | "I'm at the east entrance", "near the Core 3 lifts", "at the main door" resolve to the right node; unclear input gets a clarifying question with up to 3 options. |
| F7 | **Step-by-step guidance** (A1 + A3) | P0 | A step card shows one instruction at a time with Next / Back; the floor plan highlights the current step. |
| F8 | **Guardrail pipeline** (A2) | P0 | Input, tool and output guardrails run on every message; off-topic or unsafe input is refused politely; "no stairs" and "room exists" are enforced in code; each event appears as a visible badge in the chat. |
| F9 | **Human-in-the-loop escalation** (A2 + A1) | P0 | Saying "I'm lost" twice, or "I'm hurt, help", shows a confirmation card; on "Yes" the app shows contacts and the last known position, and the escalation is logged on the server. |
| F10 | **Demo mode** (A1 + A2) | P0 | Settings let us set a fake time and pick a location preset; the whole demo script (§7) runs inside one room; the UI clearly shows a "Demo mode" label. |
| F11 | **Outdoor journey** (A2 + A1) | P1 | User chooses walk, run or bus; the app shows leave time, arrival time, bus line and stops, the route on a map, and a status chip On time / Hurry / Late. |
| F12 | **Dynamic mode-switching** (A2) | P1 | Moving the location inside the building radius (or saying "I've arrived") switches to indoor mode and the Indoor agent, with no user button press. |
| F13 | **Real-time updates** (A2 + A1) | P1 | Without the user typing, the app sends a class reminder, a "you need to hurry" warning and the mode switch (polling every 15 s). |
| F14 | **Facing direction (compass optional)** (A3 + A2 + A1) | P1 | Without any compass, directions are still correct: at an entrance the app knows which way you face (into the building), and later turns are relative to your walking direction. The user can also say what they face ("I'm facing the lifts") to set it. If the phone has a compass (phone over HTTPS), the step card arrow follows it live. |
| F15 | **Voice** (A2 TTS, A1 mic) | P2 | The user can speak instead of typing; replies are spoken with ElevenLabs (browser voice if ElevenLabs fails). |
| F16 | **Accessible UI** (A1) | P1 | Screen reader announces replies (aria-live); large touch targets; works with keyboard; colour is never the only signal. |

### Definition of done for every task (global)
1. It meets its row in the table above.
2. It is merged to `main` through a PR (`Closes #N`) and works after `git pull` on a teammate's machine.
3. It works on localhost in a browser (frontend items) or via `curl` / pytest (backend items). Phone over HTTPS is a bonus.
4. No API keys in git. External calls have the fallback listed in §5.
5. The author posted on the board what changed and anything others need to know.

**The project is done when** the demo script in §7 runs twice in a row on localhost without errors, and the Devpost
submission (description, screenshots, short video, repo link) is in before 18:00.

## 4. Key design rules
1. **The AI never computes routes.** Code computes them (Google Routes outside, graph search inside). The AI picks
   tools and explains results in plain, short sentences.
2. **The AI never draws.** Routes come back as pixel coordinates; the frontend draws them with SVG.
3. **Map and floor plan are a panel**, opened with a toggle, never covering the chat by default.
4. **Accessibility is enforced in code**, not only in prompts.
5. **No made-up data** beyond the approved list in §5. No invented phone numbers, bus lines or rooms.

## 5. Fake / mock data (STATUS: APPROVED as below, 13:30)
Only these items may be faked. Anything not listed here must not be faked.

| # | What | Exactly how | Owner |
|---|---|---|---|
| D1 | **Timetable** (real source) | Nael gives a screenshot of his real timetable. Agent 2 (or a human) types it into `backend/app/data/timetable.json` (course, type, weekday, start, end, room, building). Only the dates are shifted: in demo mode the next class is placed relative to the demo clock. Classes in other buildings stay in the file but only Nancy Rothwell rooms get indoor guidance. The demo class is moved to **Lecture Theatre A (Nancy Rothwell, first floor)**. | A2 |
| D2 | **Demo clock** | A time picker in Settings sends `demo_time`; the backend uses it as "now". | A1 + A2 |
| D3 | **Location presets** | "Home" = real coordinates of an address the team picks; "Outside East entrance" = real coordinates on Rumford Street. Used only in demo mode instead of GPS. | A1 |
| D4 | **Facing direction without compass** | Not fake data: entrance nodes store the real direction you face when walking in (`facing_deg`). The user can also say what they face. No manual dial. | A3 + A2 |
| D5 | **Bus route** | **Real Google Routes API only.** Optional safety net: the first real response is saved to `backend/app/data/route_recorded.json` and replayed only if the live call fails during the demo. Nothing invented. | A2 |
| D6 | **LLM fallback** | If the Claude call fails, fixed sentence templates filled with real tool results. Shown as `mock` in `/api/health`. | A2 |
| D7 | **Starter stubs (first 15 min only)** | Contract-shaped example data so the three agents can start at the same time (example route East entrance → Lecture Theatre A on grey placeholder images). **Deleted when the real data lands (M1).** | A1, A2, A3 |
| D8 | **Escalation** | No fake phone numbers. The card says "Go to the reception desk on the ground floor or ask a member of staff". Confirming logs the request on our server only, and the UI says so. | A2 + A1 |

Real, not faked: the building graph (from the real floor plan), routing, turn directions, guardrails, agents,
session state, Google bus routes, Claude, ElevenLabs voice.

## 6. How we work (from the hackathon-agent-board repo)
- One repo made from the `hackathon-agent-board` template, one pinned **Message Board** issue, `tools/board` for posts.
- Post prefix: `[<human>'s Claude A<n>]`, e.g. `[Nael's Claude A2]`. Tag the owner's GitHub login.
- Keep one background `tools/board wait` running (the hooks in `.claude/` remind you).
- Branch `<issue#>-<slug>` from fresh `main`, small commits, stage only your own files (no `git add -A`), PR with
  `Closes #N`, author merges once it works, fetch + rebase before push, never force-push.
- Never edit another owner's files: ask on the board for a handoff. Humans over agents; only the team lead reassigns work.
- After merging anything others depend on (API, schema, env var), post on the board.
- **Never idle:** when a task is done, post on the board and immediately start the next one in your file. When your file
  is finished, run the demo script, fix what breaks in your own area, then ask the board what to help with.

### Owner table (paste into `AGENTS.md` §4, fill in logins)
| Area | Owner (GitHub login) | Folders |
|---|---|---|
| A1 Frontend | @login | `frontend/` |
| A2 AI agents backend | @login | `backend/app/`, `backend/requirements.txt`, `backend/.env.example`, `README.md`, `.gitignore` |
| A3 Indoor engine + data | @login | `backend/indoor/`, `data/` |
| Plans and contracts | humans only | `docs/`, `context.md`, `AGENTS.md` |

## 7. Demo script (what judges see)
1. Demo mode, time set 40 minutes before a real class from Nael's timetable, location Home. App: "Your next class is
   at 09:00 in Lecture Theatre A, Nancy Rothwell. Leave in 6 minutes."
2. "I'll take the bus." → Journey agent → map panel with the real Google bus route, chip "Hurry".
3. Switch location to "Outside East entrance" → indoor mode starts on its own (mode-switching).
4. "I'm at the East entrance and I hurt my ankle." → lift-only route to Lecture Theatre A (first floor) on the floor plan
   panel, step card "Walk straight ahead, then turn left to the Core 3 lifts" (no compass needed).
5. Off-topic or unsafe request → guardrail badge, polite refusal.
6. "I'm lost" twice → escalation card → Yes → contacts + last position.
7. Repeat a bit by voice (ElevenLabs).

## 8. Architecture and stack (short)
```
Browser (A1: React + Vite + TS)  ──/api via Vite proxy──►  FastAPI :8000
  chat · status · step card · [Map | Floor plan] panel        ├─ backend/app (A2): agents, state, guardrails,
                                                               │   escalation, calendar, Google Routes, TTS
                                                               └─ backend/indoor (A3): graph, routing, turns
                                                                   + data/ (building JSON, floor images)
```
| Part | Choice |
|---|---|
| Frontend | React 18 + Vite + TypeScript, plain CSS, `@vis.gl/react-google-maps` |
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic v2 |
| AI | **Anthropic Claude** through **LiteLLM** (one tool-calling format; switch to Gemini by changing `LLM_MODEL`). Our own small orchestrator: agents, handoffs, guardrails, session state in plain Python |
| Indoor | `networkx` (Dijkstra), `Pillow` (overlay check images) |
| Outdoor | Google Routes API `computeRoutes` (TRANSIT / WALK) |
| Voice | Browser SpeechRecognition in; ElevenLabs `eleven_flash_v2_5` out (browser voice fallback) |
| Storage | No database: in-memory state + JSON files; localStorage for settings |
| Running | **Localhost first**: backend :8000, frontend :5173 (Vite proxies `/api` and `/static`). Hosting / phone tunnel is optional, only after everything works |

## 9. Timeline (fast)
| Time | Milestone |
|---|---|
| 13:35 to 13:50 | **M0** repo from template, owner table, stubs (D7) running on localhost |
| 13:50 to 14:30 | **M1** all P0 functionalities working with real data (target finish) |
| 14:30 to 15:30 | **M2** P1 and P2 (outdoor route, mode-switch, real-time, facing direction, voice). 15:30 = latest |
| 15:30 to 16:00 | Run the demo script twice, fix only blockers, then code freeze |
| 16:00 to 18:00 | Devpost write-up, screenshots, video, rehearse; optional hosting / phone test |

## 10. Inputs only humans can provide
- **Floor plans:** a public PDF of the Nancy Rothwell Building floor plans (Ground to Third floor, 2024) exists at
  https://indico.stfc.ac.uk/event/1483/contributions/8586/attachments/2841/5116/Nancy%20Rothwell%20Building%20floorplan%202024%20v1.pdf
  Download it and give it to Agent 3 (`data/raw_plans/`). If a floor lacks detail, photograph the plan on the wall.
- `ANTHROPIC_API_KEY` (and `GEMINI_API_KEY` if we try Gemini), Google Maps key (Routes API + Maps JavaScript API),
  ElevenLabs key + voice id.
- **Timetable screenshot** (Nael) for D1.
- The "Home" demo address and a pin just outside the East entrance. Real escalation numbers (or keep the reception text).
