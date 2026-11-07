"""Load and validate the building JSON, build the networkx graph (cached)."""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import networkx as nx

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BUILDING_JSON = DATA_DIR / "building" / "nancy_rothwell.json"

LIFT_BASE_M = 15.0
LIFT_PER_FLOOR_M = 5.0
STAIRS_PER_FLOOR_M = 8.0


class BuildingDataError(ValueError):
    pass


@lru_cache(maxsize=1)
def building() -> dict:
    data = json.loads(BUILDING_JSON.read_text(encoding="utf-8"))
    ids = [n["id"] for n in data["nodes"]]
    if len(ids) != len(set(ids)):
        raise BuildingDataError("duplicate node ids")
    known = set(ids)
    for e in data["edges"]:
        for end in (e["from"], e["to"]):
            if end not in known:
                raise BuildingDataError(f"edge references unknown node {end}")
    return data


def floor_info(floor: int) -> dict:
    return next(f for f in building()["floors"] if f["floor"] == floor)


def nodes_by_id() -> dict[str, dict]:
    return {n["id"]: n for n in building()["nodes"]}


def edge_length_m(a: dict, b: dict, etype: str) -> float:
    if etype in ("lift", "stairs"):
        floors = abs(a["floor"] - b["floor"])
        if etype == "lift":
            return LIFT_BASE_M + LIFT_PER_FLOOR_M * floors
        return STAIRS_PER_FLOOR_M * floors
    ppm = floor_info(a["floor"])["pixels_per_metre"]
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"]) / ppm


@lru_cache(maxsize=2)
def build_graph(accessible: bool) -> nx.Graph:
    """Undirected walking graph; keycard edges always excluded; inaccessible edges excluded if accessible."""
    g = nx.Graph()
    nodes = nodes_by_id()
    for n in nodes.values():
        g.add_node(n["id"])
    for e in building()["edges"]:
        if e.get("keycard"):
            continue
        if accessible and not e.get("accessible", True):
            continue
        a, b = nodes[e["from"]], nodes[e["to"]]
        g.add_edge(e["from"], e["to"], weight=edge_length_m(a, b, e["type"]), type=e["type"])
    return g
