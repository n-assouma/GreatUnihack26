# Agent 3: Indoor engine and building data

**You own:** `backend/indoor/**` and `data/**`. Read `docs/PLAN.md` and `docs/CONTRACTS.md` first.
Agent 2 imports your `indoor/api.py` and mounts your `indoor/router.py`. Your dependencies (`networkx`,
`Pillow`) are already in `backend/requirements.txt`. Run and test from `backend/`.

> **Before you start:** follow `AGENTS.md` (board posts as `[<human>'s Claude A3]`, tag owners by GitHub login,
> branch + PR per issue, stage only your own files). Only fake what PLAN §5 lists. Never idle (PLAN top).
> Your work is done when it meets its rows in PLAN §3 (F4 data + routing, F5, F6, F7 steps, F14 facing) and the global definition of done.

## Goal
Turn the real Nancy Rothwell floor plans into a reliable graph (one time, no invented rooms or corridors), then provide fast, correct, accessible
routes with pixel coordinates for drawing, distances, absolute bearings and turn directions.

## M0 Skeleton (by 13:50): top priority, others depend on the shape
- `backend/indoor/__init__.py`, `api.py` with the exact functions from CONTRACTS §4 returning a **hard-coded
  fixture** (PLAN §5 D7, M0 only: an example 2-floor route East entrance → Core 3 lift → `THEATRE_A` on floor 1, deleted at M1), plus `UnknownNodeError`, `NoRouteError`.
- `router.py`: `router = APIRouter(prefix="/api/indoor")` with the 3 endpoints from CONTRACTS §3 calling `api.py`.
- Placeholder images `data/floorplans/floor_0.png` to `floor_3.png` (plain grey with a grid, Pillow) so the
  frontend can draw on something. Push immediately, tell the board "indoor stub ready".

## Files
```
backend/indoor/
  __init__.py
  api.py            # public functions (CONTRACTS §4) - the only thing Agent 2 imports
  router.py         # FastAPI APIRouter (/api/indoor/...)
  graph.py          # load + validate JSON, build networkx graph (cached)
  routing.py        # dijkstra, accessible filter, segments, steps
  directions.py     # bearings, turn classification, instruction text
  locate.py         # text → node (fuzzy match labels + aliases, difflib)
  tools/render_overlay.py   # draws nodes + edges on the floor image → data/debug/floor_N_overlay.png
  tests/test_routing.py
data/
  building/nancy_rothwell.json
  floorplans/floor_0.png, floor_1.png, floor_2.png, floor_3.png
  raw_plans/        # original photos from the human
  debug/            # overlay images for checking
```

## Step 1: get the floor plans (with your human)
Source: the public PDF "Nancy Rothwell Building floorplan 2024 v1" (Ground to Third floor, link in PLAN §10).
Ask your human to download it into `data/raw_plans/` (you may not have internet access to it). Convert each page to
PNG (`pdftoppm -png -r 150` or PyMuPDF). If a floor lacks detail, ask your human to photograph the plan on the wall.
At M0, confirm the CONTRACTS demo rooms (Lecture Theatre A on floor 1, `3A.041`) appear on the plan and tell the board. Put originals in `data/raw_plans/`. Make clean PNGs (crop, straighten,
~1200 px wide) in `data/floorplans/floor_{n}.png`. Ask which way is north on the plan → `north_offset_deg`
(the compass bearing of "up" on the image; 0 if up = north). Estimate `pixels_per_metre` from a known length
(corridor or door ≈ 0.9 m) or the plan's scale bar.

## Step 2: one-time AI conversion to JSON (you are the AI agent)
Open each floor image yourself and write `data/building/nancy_rothwell.json` (schema in CONTRACTS §5):
- Nodes at: the 3 entrances (`entrance_east`, `entrance_south`, `entrance_north` on floor 0, each with `facing_deg` =
  bearing you face when walking in, e.g. East entrance → about 270, check against the plan's north), each core's lift
  and stairs (Cores 1 to 4, ids like `f0_core3_lift`, `f3_core4_stairs`), corridor junctions and corners,
  demo rooms from CONTRACTS (`THEATRE_A` on floor 1, `3A.041`), toilets, a few landmarks (reception, cafe) with `aliases`
  people would say ("main door", "front desk").
- Edges: corridors between nearby nodes; vertical `lift` edges between the same core's lift on different floors
  (`accessible: true`); vertical `stairs` edges (`accessible: false`). Mark `keycard: true` where the plan shows
  restricted doors (AccessAble says key card restrictions between cores on floors 4 to 6).
- Keep it small but correct: only what the demo routes need, then add more if time.
- Run `tools/render_overlay.py` and **look at the overlay images**; fix wrong positions or missing links.
  Show the overlays to your human for a quick sanity check.

Known facts (AccessAble): 8 floors, Basement, Ground, 1 to 6 (lift buttons 0 = Ground, -1 = Basement);
4 cores with identical lifts and stairwells; 3 step-free entrances; East entrance on Rumford Street is closest
to Core 3; step-free throughout; link bridge to Engineering Building B on floor 2.

## Step 3: routing (`routing.py`, `directions.py`)
- Weight of same-floor edge = pixel distance / `pixels_per_metre`. Lift edge = 15 m equivalent + 5 per floor;
  stairs = 8 m per floor. Always exclude `keycard` edges. `accessible=True` → exclude edges with `accessible: false`.
- `networkx.dijkstra_path`. Raise `NoRouteError` if none.
- **Steps**: merge consecutive near-straight corridor edges into one step ("Walk 25 m along the corridor").
  Lift/stairs become one step: "Take the Core 3 lift to floor 3", `bearing_deg: null`, `via`, `target_floor`.
  Last step: `turn: "arrive"`, "Lecture Theatre A is here" (add left/right using geometry if easy).
- **Bearing** of a step from pixels: `deg = (degrees(atan2(dx, -dy)) + north_offset_deg) % 360`.
- **Turn** vs previous step: `rel = (b2 - b1 + 540) % 360 - 180`; |rel| < 25 straight, < 60 slight, < 150 left/right
  (+ = right), else turn_around. First step: b1 = `heading` if given, else the start entrance's `facing_deg`,
  else `"start"`. After a lift / stairs step, b1 = the arrival lift's `facing_deg` if set (direction you face stepping out),
  else describe by landmark ("Leave the lift and head towards the theatre signs").
- **No compass needed:** because b1 comes from the entrance and later turns are relative to the walking direction, the
  `turn` values are correct without any sensor. The compass (frontend) only refines the live arrow.
- **Segments**: split the node path by floor; `points` = node pixel coords in order; `step_indices` per segment;
  `image_url` = `/static/floorplans/floor_{n}.png`.
- **Instructions** use landmarks and labels ("past the reception", "towards the Core 3 lifts"); short, speakable.

## Step 4b: facing from words (`api.heading_towards`)
"I'm facing the lifts" → find the landmark node named in the text (same matcher as locate, nearest one on the same
floor) → bearing from `from_node` to it. Return None if unclear.

## Step 4: locate (`locate.py`)
Lower-case match of the text against node `label` + `aliases` (difflib ratio + keyword contains, e.g. "east",
"entrance", "lift", "core 3"). Return best match with confidence; `node_id: null` if confidence < 0.5,
plus up to 3 candidates.

## Tests (`pytest tests/`)
- Accessible route `entrance_east` → `THEATRE_A` contains no stairs step and uses a lift.
- Non-accessible route may use stairs; both routes end at the destination.
- Every node referenced by edges exists; graph is connected for all demo rooms from every entrance.
- `locate("I'm at the east entrance")` → `entrance_east`.
- `get_indoor_route` output validates against the CONTRACTS shape (keys and types).

## Done when
- M1 (by 14:30): real JSON for **floors 0 and 1 first** (main demo: `entrance_east` → `THEATRE_A`), then floor 3;
  real routes from all 3 entrances, accessible and normal; overlays checked by your human; tests pass.
- M2 (by 15:30): `facing_deg` on entrances, `heading_towards`, natural instructions, locate handles common phrasings, floor 2 if time.
- M3 (if time): more floors / rooms, left/right on arrival, nicer floor images.

## Ask your human for
The floor plan PDF (or photos if a floor lacks detail), which way is north on each plan, a quick check of the overlay images.
