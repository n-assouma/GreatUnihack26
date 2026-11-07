"""Bearings and relative turns."""
from __future__ import annotations

import math


def bearing(a: dict, b: dict, north_offset_deg: float = 0.0) -> float:
    """Absolute compass bearing from node a to node b (image y points down)."""
    dx, dy = b["x"] - a["x"], b["y"] - a["y"]
    return (math.degrees(math.atan2(dx, -dy)) + north_offset_deg) % 360


def relative_turn(prev_bearing: float | None, new_bearing: float) -> str:
    if prev_bearing is None:
        return "start"
    rel = (new_bearing - prev_bearing + 540) % 360 - 180
    if abs(rel) < 25:
        return "straight"
    if abs(rel) < 60:
        return "slight_right" if rel > 0 else "slight_left"
    if abs(rel) < 150:
        return "right" if rel > 0 else "left"
    return "turn_around"


TURN_WORDS = {
    "straight": "Continue straight",
    "slight_left": "Bear slightly left",
    "slight_right": "Bear slightly right",
    "left": "Turn left",
    "right": "Turn right",
    "turn_around": "Turn around",
    "start": "Walk",
}


def walk_instruction(turn: str, distance_m: float, target_label: str | None,
                     towards: bool = False, after_lift: bool = False) -> str:
    dist = max(5, int(round(distance_m / 5.0)) * 5)
    if after_lift:
        head = "Leave the lift and walk"
    elif turn == "start":
        head = "Walk straight ahead"
    elif turn == "straight":
        head = "Continue straight"
    else:
        head = f"{TURN_WORDS.get(turn, 'Walk')} and walk"
    text = f"{head} about {dist} m" if turn not in ("start", "straight") or after_lift else f"{head} for about {dist} m"
    if target_label:
        text += f" {'towards' if towards else 'to'} {target_label}"
    return text
