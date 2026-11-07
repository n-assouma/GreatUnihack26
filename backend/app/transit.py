"""Outdoor journey planning with the Google Routes API (F11, D5).

`minutes_spare` is slack before the student must set off: `leave_at - now`.
Negative means they have already missed it ("late"); under 5 minutes is "hurry".

D5 forbids inventing transport data. So: a real Google response is recorded to
`data/route_recorded.json` and replayed only if the live call fails on demo day;
with no key and no recording we return None for bus (the agent then says it cannot
check the bus) and fall back to a clearly-labelled straight-line estimate only for
walking and running, which is geometry, not invented transport.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from .models import BUILDING_LAT, BUILDING_LNG

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = (
    "routes.duration,"
    "routes.polyline.encodedPolyline,"
    "routes.legs.steps.travelMode,"
    "routes.legs.steps.staticDuration,"
    "routes.legs.steps.transitDetails,"
    "routes.legs.steps.navigationInstruction"
)
RECORDING_FILE = Path(__file__).resolve().parent / "data" / "route_recorded.json"

BUFFER_MIN = 5  # aim to arrive 5 minutes before the class starts
RUN_FACTOR = 0.6  # running takes 60% of the walking time
WALK_SPEED_MS = 1.4

_routes_ever_failed = False


def status() -> str:
    """"real" | "replay" | "mock" — for /api/health."""
    if os.getenv("ROUTE_REPLAY") == "1":
        return "replay"
    if not os.getenv("GOOGLE_MAPS_API_KEY"):
        return "mock"
    return "degraded" if _routes_ever_failed else "real"


def _load_recording(mode: str) -> dict | None:
    try:
        with RECORDING_FILE.open(encoding="utf-8") as handle:
            return json.load(handle).get(mode)
    except (OSError, json.JSONDecodeError, AttributeError):
        return None


def _save_recording(mode: str, payload: dict) -> None:
    try:
        existing: dict = {}
        if RECORDING_FILE.exists():
            with RECORDING_FILE.open(encoding="utf-8") as handle:
                existing = json.load(handle)
        existing[mode] = payload
        RECORDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        with RECORDING_FILE.open("w", encoding="utf-8") as handle:
            json.dump(existing, handle, indent=2)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        print(f"[transit] could not record route: {exc}")


def _call_google(origin: tuple[float, float], arrive_by: datetime, transit: bool) -> dict | None:
    global _routes_ever_failed

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return None

    body: dict = {
        "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
        "destination": {
            "location": {"latLng": {"latitude": BUILDING_LAT, "longitude": BUILDING_LNG}}
        },
        "travelMode": "TRANSIT" if transit else "WALK",
    }
    if transit:
        # arrivalTime is only valid for TRANSIT; Google picks a service that gets there in time.
        body["arrivalTime"] = arrive_by.astimezone().isoformat()

    try:
        response = httpx.post(
            ROUTES_URL,
            json=body,
            headers={
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": FIELD_MASK,
                "Content-Type": "application/json",
            },
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("routes"):
            return None
        _save_recording("bus" if transit else "walk", payload)
        return payload
    except (httpx.HTTPError, ValueError) as exc:
        _routes_ever_failed = True
        print(f"[transit] Google Routes call failed ({type(exc).__name__}: {exc})")
        return None


def _seconds(value: str | None) -> float:
    """Google durations look like "1234s"."""
    if not value:
        return 0.0
    try:
        return float(str(value).rstrip("s"))
    except ValueError:
        return 0.0


def _fold_walking(legs: list[dict]) -> list[dict]:
    """Collapse each run of walking steps into one leg.

    Google returns turn-by-turn walking ("Head south", "Turn left", 0.4 min each) —
    ten legs for one bus journey. Spoken aloud or shown as a list that is noise; what
    the student needs is "walk 3 min to St Mary's (Stop B)", then the bus, then the
    walk to the building (F11: leave time, arrival time, bus line and stops).
    """
    folded: list[dict] = []
    run: list[dict] = []

    def flush(next_leg: dict | None) -> None:
        if not run:
            return
        minutes = round(sum(item["duration_min"] for item in run), 1)
        if next_leg and next_leg.get("from_stop"):
            target = f" to {next_leg['from_stop']}"
        elif next_leg:
            target = " to the stop"
        else:
            target = " to the Nancy Rothwell Building"
        folded.append(
            {
                "mode": "WALK",
                "instruction": f"Walk {minutes:g} min{target}".replace(".0 min", " min"),
                "duration_min": minutes,
                "line": None,
                "from_stop": None,
                "to_stop": next_leg.get("from_stop") if next_leg else None,
                "depart_at": None,
                "arrive_at": None,
            }
        )
        run.clear()

    for leg in legs:
        if leg["mode"] == "WALK":
            run.append(leg)
            continue
        flush(leg)
        folded.append(leg)
    flush(None)
    return folded


def _legs_from_payload(payload: dict) -> list[dict]:
    legs: list[dict] = []
    for route in payload.get("routes", [])[:1]:
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                travel_mode = step.get("travelMode", "WALK")
                minutes = round(_seconds(step.get("staticDuration")) / 60, 1)
                instruction = (step.get("navigationInstruction") or {}).get("instructions", "")

                details = step.get("transitDetails") or {}
                line_info = (details.get("transitLine") or {})
                line = line_info.get("nameShort") or line_info.get("name")
                stop_details = details.get("stopDetails") or {}
                from_stop = (stop_details.get("departureStop") or {}).get("name")
                to_stop = (stop_details.get("arrivalStop") or {}).get("name")
                depart_at = details.get("localizedValues", {}) and details.get("departureTime")
                arrive_at = details.get("arrivalTime")

                if travel_mode == "TRANSIT":
                    vehicle = (line_info.get("vehicle") or {}).get("type", "BUS")
                    mode = {"BUS": "BUS", "TRAM": "TRAM", "RAIL": "TRAIN", "HEAVY_RAIL": "TRAIN"}.get(
                        vehicle, "BUS"
                    )
                    if not instruction:
                        instruction = f"Take the {line or mode.lower()}"
                        if to_stop:
                            instruction += f" to {to_stop}"
                else:
                    mode = "WALK"
                    instruction = instruction or "Walk"

                if minutes <= 0 and mode == "WALK":
                    continue  # Google emits zero-length walking steps; they add nothing spoken

                legs.append(
                    {
                        "mode": mode,
                        "instruction": instruction,
                        "duration_min": minutes,
                        "line": line,
                        "from_stop": from_stop,
                        "to_stop": to_stop,
                        "depart_at": depart_at if isinstance(depart_at, str) else None,
                        "arrive_at": arrive_at if isinstance(arrive_at, str) else None,
                    }
                )
    return _fold_walking(legs)


def _build_route(
    mode: str, total_min: float, legs: list[dict], polyline: str, class_start: datetime, now: datetime
) -> dict:
    arrive_at = class_start - timedelta(minutes=BUFFER_MIN)
    leave_at = arrive_at - timedelta(minutes=total_min)
    minutes_spare = round((leave_at - now).total_seconds() / 60, 1)

    if minutes_spare < 0:
        state = "late"
    elif minutes_spare < 5:
        state = "hurry"
    else:
        state = "on_time"

    bus_leg = next((leg for leg in legs if leg["mode"] in ("BUS", "TRAM", "TRAIN")), None)
    if bus_leg and bus_leg.get("line"):
        summary = f"Bus {bus_leg['line']}, {round(total_min)} min, arrive {arrive_at:%H:%M}"
    else:
        summary = f"{mode.capitalize()}, {round(total_min)} min, arrive {arrive_at:%H:%M}"

    return {
        "mode": mode,
        "leave_at": leave_at.isoformat(),
        "arrive_at": arrive_at.isoformat(),
        "class_start": class_start.isoformat(),
        "status": state,
        "minutes_spare": minutes_spare,
        "summary": summary,
        "legs": legs,
        "polyline": polyline,
    }


def plan(
    mode: str, origin: tuple[float, float] | None, class_start: datetime, now: datetime
) -> dict | None:
    """OutdoorRoute dict, or None when we cannot plan it honestly."""
    if origin is None:
        return None

    transit = mode == "bus"
    arrive_by = class_start - timedelta(minutes=BUFFER_MIN)

    payload = None
    if os.getenv("ROUTE_REPLAY") != "1":
        payload = _call_google(origin, arrive_by, transit)
    if payload is None:
        payload = _load_recording("bus" if transit else "walk")

    if payload is not None:
        route = payload["routes"][0]
        total_min = _seconds(route.get("duration")) / 60
        if mode == "run":
            total_min *= RUN_FACTOR
        legs = _legs_from_payload(payload)
        polyline = (route.get("polyline") or {}).get("encodedPolyline", "")
        return _build_route(mode, total_min, legs, polyline, class_start, now)

    # No key and no recording. Never invent a bus service (D5).
    if transit:
        return None

    from .state import haversine_m

    metres = haversine_m(origin[0], origin[1], BUILDING_LAT, BUILDING_LNG)
    total_min = (metres / WALK_SPEED_MS) / 60
    if mode == "run":
        total_min *= RUN_FACTOR
    legs = [
        {
            "mode": "WALK",
            "instruction": f"{mode.capitalize()} to the Nancy Rothwell Building "
            f"(straight-line estimate, no live route available)",
            "duration_min": round(total_min, 1),
            "line": None,
            "from_stop": None,
            "to_stop": None,
            "depart_at": None,
            "arrive_at": None,
        }
    ]
    return _build_route(mode, total_min, legs, "", class_start, now)
