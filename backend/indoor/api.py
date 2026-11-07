"""Public indoor API (CONTRACTS section 4). Agent 2 imports only from here."""
from __future__ import annotations

from . import directions, graph, locate as _locate, routing
from .routing import NoRouteError, UnknownNodeError

__all__ = ["UnknownNodeError", "NoRouteError", "get_building_summary", "heading_towards", "locate",
           "room_exists", "node_exists", "get_indoor_route"]


def get_building_summary() -> dict:
    b = graph.building()
    return {
        "building_id": b["building_id"],
        "name": b["name"],
        "north_offset_deg": b.get("north_offset_deg", 0),
        "floors": [{"floor": f["floor"], "label": f["label"],
                    "image_url": f"/static/floorplans/{f['image']}", "width": f["width"],
                    "height": f["height"], "pixels_per_metre": f["pixels_per_metre"]} for f in b["floors"]],
        "entrances": [{"id": n["id"], "label": n["label"], "floor": n["floor"]}
                      for n in b["nodes"] if n["type"] == "entrance"],
        "rooms": [{"id": n["id"], "label": n["label"], "floor": n["floor"]}
                  for n in b["nodes"] if n["type"] == "room"],
    }


def node_exists(node_id: str) -> bool:
    return node_id in graph.nodes_by_id()


def room_exists(room_id: str) -> bool:
    n = graph.nodes_by_id().get(room_id)
    return bool(n and n["type"] == "room")


def locate(text: str) -> dict:
    return _locate.locate(text)


def heading_towards(from_node: str, text: str) -> float | None:
    """'I'm facing the lifts' -> bearing from from_node to the landmark named in text; None if unclear."""
    nodes = graph.nodes_by_id()
    if from_node not in nodes:
        raise UnknownNodeError(from_node)
    target = _locate.find_landmark(text, near_node=from_node)
    if not target or target == from_node or nodes[target]["floor"] != nodes[from_node]["floor"]:
        return None
    north = float(graph.building().get("north_offset_deg", 0))
    return round(directions.bearing(nodes[from_node], nodes[target], north), 1)


def get_indoor_route(start: str, destination: str, accessible: bool, heading: float | None = None) -> dict:
    return routing.build_route(start, destination, accessible, heading)
