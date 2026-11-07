"""Draw graph nodes and edges on each floor image -> data/debug/floor_N_overlay.png.

Usage (from backend/): python -m indoor.tools.render_overlay [floor ...]
Optionally pass --route START DEST to draw an actual route instead of the whole graph.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

from indoor import graph

DATA = Path(__file__).resolve().parents[3] / "data"
COLORS = {"entrance": (220, 0, 0), "lift": (0, 90, 220), "stairs": (200, 120, 0), "room": (0, 150, 0),
          "landmark": (150, 0, 150)}


def render(floor: int, highlight: list[str] | None = None) -> Path:
    b = graph.building()
    info = next(f for f in b["floors"] if f["floor"] == floor)
    img = Image.open(DATA / "floorplans" / info["image"]).convert("RGB")
    d = ImageDraw.Draw(img)
    nodes = {n["id"]: n for n in b["nodes"]}
    hl_edges = set(zip(highlight, highlight[1:])) if highlight else set()
    for e in b["edges"]:
        a, c = nodes[e["from"]], nodes[e["to"]]
        if a["floor"] != floor or c["floor"] != floor:
            continue
        on_route = (e["from"], e["to"]) in hl_edges or (e["to"], e["from"]) in hl_edges
        # Thick bright line with a thin dark outline so it shows on any plan colour.
        col = (255, 0, 200) if on_route else (255, 215, 0)
        pts = [(a["x"], a["y"]), (c["x"], c["y"])]
        d.line(pts, fill=(0, 0, 0), width=14 if on_route else 12)
        d.line(pts, fill=col, width=9 if on_route else 8)
    for n in b["nodes"]:
        if n["floor"] != floor:
            continue
        col = COLORS.get(n["type"], (0, 0, 0))
        r = 8 if n["type"] in COLORS else 5
        d.ellipse([n["x"] - r, n["y"] - r, n["x"] + r, n["y"] + r], fill=col, outline=(255, 255, 255))
        d.text((n["x"] + 9, n["y"] - 14), n["id"], fill=(0, 0, 0))
    out = DATA / "debug" / f"floor_{floor}_overlay.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def main(argv: list[str]) -> None:
    floors = [int(a) for a in argv if a.isdigit()] or [f["floor"] for f in graph.building()["floors"]]
    for f in floors:
        print(render(f))


if __name__ == "__main__":
    main(sys.argv[1:])
