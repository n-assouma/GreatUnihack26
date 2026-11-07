"""Public indoor API (CONTRACTS section 4). Agent 2 imports only from here.

M0 STUB (PLAN D7): returns a hard-coded example route. Deleted at M1 when the
real graph lands.
"""
from __future__ import annotations

import copy

BUILDING_ID = "nancy_rothwell"


class UnknownNodeError(ValueError):
    """Raised when a node or room id does not exist."""


class NoRouteError(RuntimeError):
    """Raised when no path exists between two nodes."""


_FLOORS = [
    {"floor": n, "label": label, "image_url": f"/static/floorplans/floor_{n}.png",
     "width": 1200, "height": 800, "pixels_per_metre": 8.0}
    for n, label in enumerate(["Ground", "First", "Second", "Third"])
]
_ENTRANCES = [
    {"id": "entrance_east", "label": "East entrance (Rumford Street)", "floor": 0},
    {"id": "entrance_south", "label": "South entrance (Booth Street East)", "floor": 0},
    {"id": "entrance_north", "label": "North entrance", "floor": 0},
]
_ROOMS = [
    {"id": "THEATRE_A", "label": "Lecture Theatre A", "floor": 1},
    {"id": "3A.041", "label": "Room 3A.041", "floor": 3},
]
_ROOM_IDS = {r["id"] for r in _ROOMS}
_NODE_IDS = {e["id"] for e in _ENTRANCES} | _ROOM_IDS | {"f0_core3_lift", "f1_core3_lift"}

# Example fixture: East entrance -> Core 3 lift -> THEATRE_A (floor 1).
_FIXTURE = {
    "start_node": "entrance_east",
    "destination_id": "THEATRE_A",
    "accessible": True,
    "total_distance_m": 65.0,
    "steps": [
        {"index": 0, "instruction": "Walk straight ahead to the Core 3 lifts",
         "floor": 0, "from_node": "entrance_east", "to_node": "f0_core3_lift",
         "distance_m": 25.0, "bearing_deg": 270.0, "turn": "start", "via": None,
         "target_floor": None},
        {"index": 1, "instruction": "Take the Core 3 lift to floor 1",
         "floor": 0, "from_node": "f0_core3_lift", "to_node": "f1_core3_lift",
         "distance_m": 0.0, "bearing_deg": None, "turn": "lift", "via": "lift",
         "target_floor": 1},
        {"index": 2, "instruction": "Leave the lift, turn left and walk 40 m to Lecture Theatre A",
         "floor": 1, "from_node": "f1_core3_lift", "to_node": "THEATRE_A",
         "distance_m": 40.0, "bearing_deg": 180.0, "turn": "left", "via": None,
         "target_floor": None},
        {"index": 3, "instruction": "Lecture Theatre A is here",
         "floor": 1, "from_node": "THEATRE_A", "to_node": "THEATRE_A",
         "distance_m": 0.0, "bearing_deg": None, "turn": "arrive", "via": None,
         "target_floor": None},
    ],
    "segments": [
        {"floor": 0, "image_url": "/static/floorplans/floor_0.png",
         "points": [[1120, 410], [900, 410]], "step_indices": [0, 1]},
        {"floor": 1, "image_url": "/static/floorplans/floor_1.png",
         "points": [[900, 410], [900, 200], [600, 200]], "step_indices": [2, 3]},
    ],
}


def get_building_summary() -> dict:
    return {
        "building_id": BUILDING_ID,
        "name": "Nancy Rothwell Building",
        "north_offset_deg": 0,
        "floors": copy.deepcopy(_FLOORS),
        "entrances": copy.deepcopy(_ENTRANCES),
        "rooms": copy.deepcopy(_ROOMS),
    }


def node_exists(node_id: str) -> bool:
    return node_id in _NODE_IDS


def room_exists(room_id: str) -> bool:
    return room_id in _ROOM_IDS


def heading_towards(from_node: str, text: str) -> float | None:
    """Bearing from from_node to the landmark named in text, None if unclear (stub: lifts only)."""
    if not node_exists(from_node):
        raise UnknownNodeError(from_node)
    return 270.0 if "lift" in text.lower() else None


def locate(text: str) -> dict:
    t = text.lower()
    for ent in _ENTRANCES:
        if ent["id"].split("_")[1] in t:
            return {"node_id": ent["id"], "confidence": 0.9,
                    "candidates": [{"node_id": ent["id"], "label": ent["label"],
                                    "floor": ent["floor"]}]}
    return {"node_id": None, "confidence": 0.0,
            "candidates": [{"node_id": e["id"], "label": e["label"], "floor": e["floor"]}
                           for e in _ENTRANCES]}


def get_indoor_route(start: str, destination: str, accessible: bool,
                     heading: float | None = None) -> dict:
    for n in (start, destination):
        if not node_exists(n):
            raise UnknownNodeError(n)
    if destination not in _ROOM_IDS:
        raise NoRouteError(f"{start} -> {destination}")
    route = copy.deepcopy(_FIXTURE)
    route["start_node"] = start
    route["destination_id"] = destination
    route["accessible"] = accessible
    return route
