"""Dijkstra routing, step merging, floor segments."""
from __future__ import annotations

import re

import networkx as nx

from . import directions, graph


class UnknownNodeError(ValueError):
    """Raised when a node or room id does not exist."""


class NoRouteError(RuntimeError):
    """Raised when no path exists between two nodes."""


def _landmark_label(node: dict) -> str | None:
    if node["type"] in ("room", "landmark", "entrance", "lift", "toilet"):
        return re.sub(r"\s*\([^)]*floor\)", "", node["label"])  # "Core 4 lifts (ground floor)" -> "Core 4 lifts"
    return None


def find_path(start: str, destination: str, accessible: bool) -> list[str]:
    nodes = graph.nodes_by_id()
    for n in (start, destination):
        if n not in nodes:
            raise UnknownNodeError(n)
    g = graph.build_graph(accessible)
    try:
        return nx.dijkstra_path(g, start, destination, weight="weight")
    except nx.NetworkXNoPath as e:
        raise NoRouteError(f"{start} -> {destination}") from e


def build_route(start: str, destination: str, accessible: bool, heading: float | None = None) -> dict:
    nodes = graph.nodes_by_id()
    north = float(graph.building().get("north_offset_deg", 0))
    path = find_path(start, destination, accessible)
    g = graph.build_graph(accessible)

    # Split path into legs: runs of same-floor walking, and single vertical moves.
    legs: list[dict] = []
    for i, (a_id, b_id) in enumerate(zip(path, path[1:]), start=1):
        a, b = nodes[a_id], nodes[b_id]
        etype = g[a_id][b_id]["type"]
        dist = g[a_id][b_id]["weight"]
        vertical = etype in ("lift", "stairs")
        if vertical:
            last = legs[-1] if legs else None
            if last and last["vertical"] and last["type"] == etype and last["to"] == a_id:
                # Several floors in one go: one "Take the lift to floor 3" step.
                last.update({"to": b_id, "target_floor": b["floor"], "to_idx": i})
                continue
            legs.append({"vertical": True, "type": etype, "from": a_id, "to": b_id, "dist": 0.0,
                         "floor": a["floor"], "target_floor": b["floor"], "to_idx": i})
            continue
        brg = directions.bearing(a, b, north)
        last = legs[-1] if legs else None
        if last and not last["vertical"] and abs(((brg - last["bearing"] + 540) % 360) - 180) < 25 \
                and last["floor"] == a["floor"] and nodes[last["to"]]["type"] in ("junction", "corridor"):
            last["to"] = b_id
            last["to_idx"] = i
            last["dist"] += dist
            last["bearing"] = brg
        else:
            legs.append({"vertical": False, "from": a_id, "to": b_id, "dist": dist, "bearing": brg,
                         "floor": a["floor"], "to_idx": i})

    # Fold tiny hops (a few metres, e.g. just inside a door) into the next walking leg.
    folded: list[dict] = []
    k = 0
    while k < len(legs):
        leg = legs[k]
        nxt = legs[k + 1] if k + 1 < len(legs) else None
        if (not leg["vertical"] and leg["dist"] < 7 and nxt and not nxt["vertical"]
                and nxt["floor"] == leg["floor"]):
            folded.append({**nxt, "from": leg["from"], "dist": leg["dist"] + nxt["dist"]})
            k += 2
        else:
            folded.append(leg)
            k += 1
    legs = folded

    # Initial facing direction.
    start_node = nodes[start]
    prev = heading if heading is not None else start_node.get("facing_deg")
    steps: list[dict] = []
    for leg in legs:
        idx = len(steps)
        if leg["vertical"]:
            lift = leg["type"] == "lift"
            core = nodes[leg["from"]]["label"].split(" (")[0].replace(" lifts", "")
            text = (f"Take the {core} lift to floor {leg['target_floor']}" if lift
                    else f"Take the stairs to floor {leg['target_floor']}")
            steps.append({"index": idx, "instruction": text, "floor": leg["floor"],
                          "from_node": leg["from"], "to_node": leg["to"], "distance_m": 0.0,
                          "bearing_deg": None, "turn": leg["type"], "via": leg["type"],
                          "target_floor": leg["target_floor"]})
            prev = nodes[leg["to"]].get("facing_deg")
            continue
        turn = directions.relative_turn(prev, leg["bearing"])
        label, towards = None, False
        for j in range(leg["to_idx"], len(path)):
            label = _landmark_label(nodes[path[j]])
            if label:
                towards = j != leg["to_idx"]
                break
        after = steps[-1]["turn"] if prev is None and steps and steps[-1]["turn"] in ("lift", "stairs") else None
        steps.append({"index": idx, "instruction": directions.walk_instruction(
                          turn, leg["dist"], label, towards=towards, after=after),
                      "floor": leg["floor"], "from_node": leg["from"], "to_node": leg["to"],
                      "distance_m": round(leg["dist"], 1), "bearing_deg": round(leg["bearing"], 1),
                      "turn": turn, "via": None, "target_floor": None})
        prev = leg["bearing"]
    dest = nodes[destination]
    steps.append({"index": len(steps), "instruction": f"{dest['label']} is here", "floor": dest["floor"],
                  "from_node": destination, "to_node": destination, "distance_m": 0.0,
                  "bearing_deg": None, "turn": "arrive", "via": None, "target_floor": None})

    # Segments: split the node path by floor, map each step to its segment.
    segments: list[dict] = []
    for node_id in path:
        n = nodes[node_id]
        if not segments or segments[-1]["floor"] != n["floor"]:
            segments.append({"floor": n["floor"],
                             "image_url": f"/static/floorplans/{graph.floor_info(n['floor'])['image']}",
                             "points": [], "step_indices": []})
        segments[-1]["points"].append([n["x"], n["y"]])
    for s in steps:
        floor_segments = [i for i, seg in enumerate(segments) if seg["floor"] == s["floor"]]
        if s["turn"] in ("lift", "stairs"):
            candidates = [i for i in floor_segments if segments[i]["points"][-1] ==
                          [nodes[s["from_node"]]["x"], nodes[s["from_node"]]["y"]]]
            seg_i = candidates[0] if candidates else floor_segments[0]
        else:
            seg_i = floor_segments[-1] if s["turn"] == "arrive" else next(
                (i for i in floor_segments if [nodes[s["from_node"]]["x"], nodes[s["from_node"]]["y"]]
                 in segments[i]["points"]), floor_segments[0])
        segments[seg_i]["step_indices"].append(s["index"])

    # Floors you only pass through (no step on them) are not drawn.
    segments = [s for s in segments if s["step_indices"]]

    total = sum(g[a][b]["weight"] for a, b in zip(path, path[1:]) if g[a][b]["type"] not in ("lift", "stairs"))
    return {"start_node": start, "destination_id": destination, "accessible": accessible,
            "total_distance_m": round(total, 1), "steps": steps, "segments": segments}
