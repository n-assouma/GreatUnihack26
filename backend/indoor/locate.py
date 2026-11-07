"""Free text -> node (fuzzy match on labels and aliases)."""
from __future__ import annotations

import difflib
import re

from . import graph

NOISE = re.compile(r"\b(i m|i'?m|i am|im|at|near|by|the|in|outside|inside|next to|beside|facing|towards|toward|to|is|a|an|my|of)\b")
MIN_CONFIDENCE = 0.5


def _norm(text: str) -> str:
    t = re.sub(r"[^a-z0-9. ]", " ", text.lower())
    t = NOISE.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def _score(query: str, node: dict) -> float:
    names = [node["label"], *node.get("aliases", []), node["id"].replace("_", " ")]
    best = 0.0
    for name in names:
        n = _norm(name)
        if not n:
            continue
        if n == query:
            return 1.0
        if n in query or query in n and len(query) >= 4:
            best = max(best, 0.85 if n in query else 0.7)
        best = max(best, difflib.SequenceMatcher(None, query, n).ratio())
        qtok, ntok = set(query.split()), set(n.split())
        if qtok and ntok:
            best = max(best, 0.9 * len(qtok & ntok) / max(len(qtok), len(ntok)))
    return best


FLOOR_PHRASE = re.compile(r"\b(on|at|in)?\s*(the )?(ground|first|second|third|1st|2nd|3rd) floor\b|\b(floor|level)\s*\d\b")


def locate(text: str) -> dict:
    query = _norm(FLOOR_PHRASE.sub(" ", text.lower()))
    if not query:
        return {"node_id": None, "confidence": 0.0, "candidates": []}
    scored = []
    for n in graph.building()["nodes"]:
        if n["type"] == "junction":
            continue
        scored.append((_score(query, n), n))
    scored.sort(key=lambda s: -s[0])
    cands = [{"node_id": n["id"], "label": n["label"], "floor": n["floor"]} for s, n in scored[:3] if s > 0.2]
    top = scored[0][0] if scored else 0.0
    if top < MIN_CONFIDENCE:
        return {"node_id": None, "confidence": round(top, 2), "candidates": cands}
    tied = [n for s, n in scored if s >= top - 0.05]
    if len(tied) > 1:
        # Same place on several floors (for example "Core 3 lifts"): use a floor named in the text,
        # else assume the ground floor (everyone enters there) with reduced confidence.
        floor = _floor_in_text(text)
        same_place = {_strip_floor(n["label"]) for n in tied}
        if len(same_place) == 1:
            pick = next((n for n in tied if n["floor"] == floor), None) if floor is not None else None
            if pick:
                return {"node_id": pick["id"], "confidence": round(top, 2), "candidates": cands}
            ground = next((n for n in tied if n["floor"] == 0), None)
            if ground:
                return {"node_id": ground["id"], "confidence": min(round(top, 2), 0.6), "candidates": cands}
        return {"node_id": None, "confidence": round(top, 2), "candidates": cands}
    return {"node_id": scored[0][1]["id"], "confidence": round(top, 2), "candidates": cands}


FLOOR_WORDS = {"ground": 0, "first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3}


def _strip_floor(label: str) -> str:
    return re.sub(r"\s*\(.*?floor\)", "", label)


def _floor_in_text(text: str) -> int | None:
    t = text.lower()
    m = re.search(r"floor\s*(\d)|level\s*(\d)", t)
    if m:
        return int(m.group(1) or m.group(2))
    for word, n in FLOOR_WORDS.items():
        if re.search(rf"\b{word}\b", t):
            return n
    return None


def find_landmark(text: str, near_node: str | None = None) -> str | None:
    """Best landmark/lift/room node named in text; ties broken by distance to near_node on the same floor."""
    query = _norm(text)
    nodes = graph.nodes_by_id()
    scored = [(_score(query, n), n) for n in nodes.values() if n["type"] != "junction"]
    scored = [(s, n) for s, n in scored if s >= MIN_CONFIDENCE]
    if not scored:
        return None
    top = max(s for s, _ in scored)
    best = [n for s, n in scored if s >= top - 0.05]
    if near_node and near_node in nodes:
        ref = nodes[near_node]
        same = [n for n in best if n["floor"] == ref["floor"]] or best
        best = sorted(same, key=lambda n: (n["x"] - ref["x"]) ** 2 + (n["y"] - ref["y"]) ** 2)
    return best[0]["id"]
