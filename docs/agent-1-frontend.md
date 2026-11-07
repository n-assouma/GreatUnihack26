# Agent 1: Frontend

**You own:** `frontend/**` only.
**You talk to:** the backend only through the HTTP API in CONTRACTS. Until it is up, use the D7 stubs (PLAN §5).

> **Before you start:** follow `AGENTS.md` (board posts as `[<human>'s Claude A1]`, tag owners by GitHub login,
> branch + PR per issue, stage only your own files). Only fake what PLAN §5 lists. Never idle (PLAN top).
> Your work is done when it meets its rows in PLAN §3 (F4 drawing, F7, F9 card, F10, F11 map, F13, F14, F15 mic, F16)
> and the global definition of done. **Run on localhost**; phone / hosting only at the end if time.

## Goal
A mobile-first, accessible web app: chat with the assistant, see the class status, follow indoor steps
(with a live compass arrow when the device has one), and open a **Map** or **Floor plan** panel that takes part of the screen
(never full screen by default).

## M0 Skeleton (by 13:50)
- `npm create vite@latest frontend -- --template react-ts`, install `@vis.gl/react-google-maps uuid`.
- `vite.config.ts`: proxy `/api` and `/static` to `http://localhost:8000`; `server.host = true`.
- `src/api.ts`: typed client for every endpoint in CONTRACTS. If `VITE_USE_MOCKS=1` (or a request fails),
  return fixtures from `src/mocks/` (write one fixture per type: ChatResponse with outdoor route, ChatResponse
  with indoor route of 2 floors, BuildingSummary, Escalation). Use plain grey placeholder images for floor plans. These are M0 only: switch to the real backend at M1 and keep fixtures only as an offline fallback copied from real responses.
- `src/types.ts`: copy the TypeScript types from CONTRACTS exactly.
- App shell renders with mocks.

## Layout (phone portrait first, also fine on laptop)
```
┌──────────────────────────────┐
│ StatusBar: next class · room · status chip (On time / Hurry / Late) · phase · settings ⚙ │
├──────────────────────────────┤
│ StepCard (only in indoor phase): big arrow + "Turn left" + instruction,      │
│ [Back] [Next step] buttons, floor badge                                     │
├──────────────────────────────┤
│ Panel (collapsible, ~40% height on phone, right column on laptop):          │
│ tabs [Map] [Floor plan] [Hide]                                               │
├──────────────────────────────┤
│ ChatPanel: messages (agent name tag, guardrail badges), input, 🎤 mic, send │
└──────────────────────────────┘
EscalationCard appears as an overlay card when ui.escalation is set.
```

## Components
- **StatusBar**: from `ui.next_class` and `ui.outdoor_route.status`. Colour + text (never colour alone).
- **ChatPanel**: message list with `aria-live="polite"`; show which agent replied (Coordinator / Journey / Indoor)
  as a small tag; show `guardrails[]` as small badges ("Guardrail: kept on topic"), judges must see them.
- **Panel**: tabs Map / Floor plan / Hide. Auto-switch only when `ui.open_panel` changes, user choice wins after.
- **MapPanel**: Google Map (`VITE_GOOGLE_MAPS_API_KEY`), decode `outdoor_route.polyline`
  (`google.maps.geometry.encoding.decodePath`, load the `geometry` library), user dot, building marker,
  leg list under the map (bus line, stops, times). No key → show leg list only.
- **FloorPlanPanel**: `<img>` of the floor + `<svg viewBox="0 0 width height">` absolutely on top,
  sizes from `BuildingSummary.floors`. Draw `segments[].points` as a thick polyline (animated dashes OK),
  start marker, destination marker, highlight the part for the current step, "you are here" dot at the
  current step's `from_node` point. Floor tabs; auto-select the floor of the current step.
  Support pinch / zoom with simple CSS transform if time allows.
- **StepCard**: current step from `indoor_route.steps[current_step]`. Big arrow rotated by live relative turn
  (see below). Buttons Back / Next (also voice: "next"). Send `current_step` in every request context.
- **EscalationCard** (no invented phone numbers, see PLAN §5 D8): if `needs_confirmation` → "Shall I contact reception?" [Yes] [No] → `POST /api/escalation/confirm`.
  Then show contacts with `tel:` links and a "Copy my location" button (text of `last_known`).
- **SettingsSheet**: toggles `no_stairs`, `visual_impairment`; transport preference; voice on/off; **Demo mode**:
  time picker (sets `demo_time`) and location presets: "Home" = DEMO_HOME_LAT_LNG,
  "Outside East entrance" = OUTSIDE_EAST_LAT_LNG, "Real GPS". Save settings in localStorage.

## Hooks
- **useCompass**: iOS: `DeviceOrientationEvent.requestPermission()` from a button tap, then read
  `event.webkitCompassHeading`. Android/Chrome: listen to `deviceorientationabsolute`, heading = `360 - alpha`.
  Smooth (average last 5). Return `null` if unavailable (laptops, or phone without HTTPS). **The compass is optional**:
  with `null` the app still works, because the backend's step `turn` values are relative to the walking direction and
  start from the entrance's known facing direction. The user can also type or say what they face ("I'm facing the lifts").
  Show a small "Compass on / off" indicator and a "Use compass" button (needed for the iOS permission prompt).
- **useGeolocation**: `watchPosition`, overridden by demo preset.
- **useTick**: `POST /api/tick` every 15 s and on location / preset / demo_time change; merge non-null fields.
- **useSpeech**: input with `SpeechRecognition || webkitSpeechRecognition` (en-GB). Output: `POST /api/tts`,
  play the mp3; if it fails, `speechSynthesis`. Auto-speak replies when voice on or `visual_impairment`.

## Live relative turn (compass) in the StepCard
```
rel = (step.bearing_deg - heading + 540) % 360 - 180   // -180..180, + = right
|rel| < 25 → "Straight ahead" · 25..60 → "Slight left/right" · 60..150 → "Turn left/right" · > 150 → "Turn around"
```
If `heading` is null or `bearing_deg` is null, show `step.turn` from the backend instead.
Rotate the arrow icon by `rel` degrees.

## Accessibility checklist
- All buttons ≥ 44 px, visible focus, labels on icon buttons, high contrast theme, text ≥ 16 px.
- Every reply in an `aria-live` region; the StepCard text is also read aloud when the step changes.
- Works with keyboard only and with screen readers (VoiceOver / TalkBack).

## Done when
- M1 (by 14:30): chat against the real backend with agent tags and guardrail badges; StepCard + FloorPlanPanel draw a real
  route from Agent 3; escalation card; demo mode (time + location presets).
- M2 (by 15:30): map route, tick polling, compass arrow when available, voice in and out, accessibility polish.
  The PLAN demo script runs on localhost.

## Ask your human for
`VITE_GOOGLE_MAPS_API_KEY`, the Home and East entrance coordinates (D3). A tunnel URL only if you test on a phone at the end.
