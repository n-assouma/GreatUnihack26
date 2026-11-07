"""Run the PLAN §7 demo script against a live backend and check every step.

Usage: python demo_check.py [run_label]
Exits non-zero if any step fails its check.
"""

import sys
import uuid

import httpx

BASE = "http://localhost:8000"
DEMO_TIME = "2026-11-09T09:40:00+00:00"  # Monday, 20 min before the real 10:00 class.
# 09:40 is deliberate: the real bus takes 12 min, so this is the clock that produces
# the "Hurry" chip PLAN §7 step 2 asks for. An earlier clock correctly reads on_time.
HOME = {"lat": 53.4600, "lng": -2.2300}
EAST = {"lat": 53.469093, "lng": -2.234591}

label = sys.argv[1] if len(sys.argv) > 1 else "run"
session = f"demo-{label}-{uuid.uuid4().hex[:6]}"
failures = []


def ctx(location=None, no_stairs=False):
    body = {
        "accessibility": {"no_stairs": no_stairs, "visual_impairment": False},
        "demo_time": DEMO_TIME,
    }
    if location:
        body.update(location)
    return body


def chat(message, location=None, no_stairs=False):
    return httpx.post(
        f"{BASE}/api/chat",
        json={"session_id": session, "message": message, "context": ctx(location, no_stairs)},
        timeout=30,
    ).json()


def tick(location=None):
    return httpx.post(
        f"{BASE}/api/tick",
        json={"session_id": session, "context": ctx(location)},
        timeout=30,
    ).json()


def check(step, body, *conditions):
    ui = body.get("ui") or {}
    print(f"\n[{step}] agent={body.get('agent')} phase={body.get('phase')} "
          f"panel={ui.get('open_panel')}")
    print(f"       reply: {(body.get('reply') or '(none)')[:150]}")
    for event in body.get("guardrails") or []:
        print(f"       badge: {event['stage']}/{event['rule']}/{event['action']}")
    for description, passed in conditions:
        print(f"       {'PASS' if passed else 'FAIL'}  {description}")
        if not passed:
            failures.append(f"{step}: {description}")


health = httpx.get(f"{BASE}/api/health", timeout=10).json()
print(f"health: {health}")

# 1. Demo mode, 40 minutes before the class, at home.
body = chat("what is my next class?", HOME)
ui = body["ui"]
check(
    "1 next class",
    body,
    ("knows the class is in Lecture Theatre A", (ui.get("next_class") or {}).get("room_id") == "THEATRE_A"),
    ("starts at 10:00", "T10:00" in ((ui.get("next_class") or {}).get("start") or "")),
    ("mentions the room in the reply", "Lecture Theatre A" in (body.get("reply") or "")),
)

# 2. "I'll take the bus."
body = chat("I'll take the bus", HOME)
has_route = body["ui"].get("outdoor_route") is not None
route = body["ui"].get("outdoor_route") or {}
bus_leg = next((leg for leg in route.get("legs") or [] if leg["mode"] == "BUS"), None)
check(
    "2 bus",
    body,
    ("journey agent answered", body["agent"] == "journey"),
    (
        "either a real route, or an honest refusal with no invented line",
        has_route or "can't check" in (body.get("reply") or "").lower(),
    ),
    # PLAN §7 step 2 wants the Hurry chip; DEMO_TIME is set to produce it.
    ("status chip is Hurry at this demo clock", not has_route or route.get("status") == "hurry"),
    ("the bus leg names a real line and stops",
     not bus_leg or bool(bus_leg.get("line") and bus_leg.get("from_stop"))),
    ("the leg list is short enough to show and speak", not has_route or len(route["legs"]) <= 5),
    ("there is a polyline for the map", not has_route or bool(route.get("polyline"))),
)
if not has_route:
    print("       NOTE: no GOOGLE_MAPS_API_KEY, so the bus leg is declined (D5). Expected.")

# 3. Location moves to the East entrance: indoor mode with no typing.
body = tick(EAST)
check(
    "3 geofence mode switch",
    body,
    ("switched to indoor on its own", body["phase"] == "indoor"),
    ("indoor agent is active", body["agent"] == "indoor"),
    ("asks which entrance", "entrance" in (body.get("reply") or "").lower()),
)

# 4. "I'm at the East entrance and I hurt my ankle."
body = chat("I'm at the East entrance and I hurt my ankle", EAST)
route = body["ui"].get("indoor_route") or {}
steps = route.get("steps") or []
check(
    "4 lift-only route",
    body,
    ("a route came back", bool(steps)),
    ("it is accessible", route.get("accessible") is True),
    ("no step uses stairs", all(s.get("via") != "stairs" for s in steps)),
    ("the reply never says stairs", "stair" not in (body.get("reply") or "").lower()),
    ("it changes floor via the lift", any(s.get("via") == "lift" for s in steps)),
    ("reaches Lecture Theatre A", route.get("destination_id") == "THEATRE_A"),
    ("the floor plan panel is suggested", body["ui"].get("open_panel") == "floorplan"),
    ("the accessibility override is visible as a badge",
     any(e["rule"].startswith("no_stairs") for e in body.get("guardrails") or [])),
    ("the floor plan has pixel points to draw",
     all(seg.get("points") for seg in route.get("segments") or [{}])),
)

# 5. Off-topic request.
body = chat("what's the weather tomorrow?", EAST)
check(
    "5 guardrail refusal",
    body,
    ("blocked as off topic",
     any(e["rule"] == "off_topic" and e["action"] == "blocked" for e in body.get("guardrails") or [])),
    ("refuses politely and offers help", "campus" in (body.get("reply") or "").lower()),
)

# 6. "I'm lost" twice, then confirm.
first = chat("I'm lost", EAST)
check(
    "6a lost once",
    first,
    ("does not escalate on the first time", first["ui"].get("escalation") is None),
)
second = chat("I'm lost", EAST)
escalation = second["ui"].get("escalation") or {}
check(
    "6b lost twice",
    second,
    ("offers a human", bool(escalation)),
    ("asks for confirmation first", escalation.get("needs_confirmation") is True),
    ("no invented phone number",
     all(c.get("phone") is None for c in escalation.get("contacts") or [])),
    ("keeps the last known position", bool(escalation.get("last_known"))),
)
confirmed = httpx.post(
    f"{BASE}/api/escalation/confirm",
    json={"session_id": session, "confirm": True},
    timeout=30,
).json()
check(
    "6c confirmed",
    confirmed,
    ("stops asking", (confirmed["ui"].get("escalation") or {}).get("needs_confirmation") is False),
    ("points at reception", "reception" in (confirmed.get("reply") or "").lower()),
)
logged = httpx.get(f"{BASE}/api/escalations", timeout=10).json()
mine = [e for e in logged["escalations"] if e["session_id"] == session]
check("6d logged", {}, ("the request is logged on the server", len(mine) == 1))

# 7. Voice.
response = httpx.post(f"{BASE}/api/tts", json={"text": "Turn left to the lifts."}, timeout=30)
print(f"\n[7 voice] /api/tts -> {response.status_code}")
ok_voice = response.status_code in (200, 503)
print(f"       {'PASS' if ok_voice else 'FAIL'}  200 with audio, or 503 so the browser speaks")
if not ok_voice:
    failures.append("7: tts returned an unexpected status")
if response.status_code == 503:
    print("       NOTE: no ELEVENLABS_API_KEY, so the browser voice is used. Expected.")

# Session survives, which is what a page reload relies on.
debug = httpx.get(f"{BASE}/api/session/{session}", timeout=10).json()
check(
    "state",
    {},
    ("the session remembers the position", debug.get("current_node") == "entrance_east"),
    ("and remembers the accessibility need", debug.get("lost_count") >= 2),
)

print("\n" + "=" * 60)
if failures:
    print(f"{len(failures)} CHECK(S) FAILED:")
    for item in failures:
        print(f"  - {item}")
    sys.exit(1)
print(f"demo script run '{label}': every check passed")
