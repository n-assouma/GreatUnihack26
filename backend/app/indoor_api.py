"""Safe access to Agent 3's indoor engine (CONTRACTS §4).

Agent 3 owns `backend/indoor/`; we only import it. This shim exists so that a
broken or half-written `indoor.api` — likely while they are swapping the stub for
the real graph — degrades to "I can't check the building right now" instead of
taking the whole backend down mid-demo.

`import indoor` only resolves when the server is started from `backend/`, which is
what CONTRACTS §3 and the README both specify.
"""

from __future__ import annotations

try:  # pragma: no cover - exercised by whether Agent 3's module is importable
    from indoor import api as _api

    UnknownNodeError = _api.UnknownNodeError
    NoRouteError = _api.NoRouteError
except Exception as exc:  # noqa: BLE001
    print(f"[indoor_api] indoor engine unavailable ({type(exc).__name__}: {exc})")
    _api = None

    class UnknownNodeError(ValueError):
        """Stand-in so callers can always catch this."""

    class NoRouteError(RuntimeError):
        """Stand-in so callers can always catch this."""


def available() -> bool:
    return _api is not None


def status() -> str:
    """"real" | "mock" — for /api/health."""
    return "real" if available() else "mock"


def node_exists(node_id: str) -> bool:
    if _api is None or not node_id:
        return False
    try:
        return bool(_api.node_exists(node_id))
    except Exception:  # noqa: BLE001
        return False


def room_exists(room_id: str) -> bool:
    if _api is None or not room_id:
        return False
    try:
        return bool(_api.room_exists(room_id))
    except Exception:  # noqa: BLE001
        return False


def locate(text: str) -> dict:
    if _api is None:
        return {"node_id": None, "confidence": 0.0, "candidates": []}
    try:
        return _api.locate(text) or {"node_id": None, "confidence": 0.0, "candidates": []}
    except Exception as exc:  # noqa: BLE001
        print(f"[indoor_api] locate failed: {exc}")
        return {"node_id": None, "confidence": 0.0, "candidates": []}


def heading_towards(from_node: str, text: str) -> float | None:
    if _api is None:
        return None
    try:
        return _api.heading_towards(from_node, text)
    except (UnknownNodeError, ValueError):
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"[indoor_api] heading_towards failed: {exc}")
        return None


def get_indoor_route(
    start: str, destination: str, accessible: bool, heading: float | None = None
) -> dict:
    """Raises UnknownNodeError / NoRouteError; callers must handle both."""
    if _api is None:
        raise NoRouteError("the indoor engine is not available")
    return _api.get_indoor_route(start, destination, accessible, heading)


def get_building_summary() -> dict:
    if _api is None:
        return {"building_id": "", "name": "", "floors": [], "entrances": [], "rooms": []}
    try:
        return _api.get_building_summary() or {}
    except Exception as exc:  # noqa: BLE001
        print(f"[indoor_api] get_building_summary failed: {exc}")
        return {"building_id": "", "name": "", "floors": [], "entrances": [], "rooms": []}


def entrance_labels() -> list[str]:
    return [str(e.get("label", "")) for e in get_building_summary().get("entrances", [])]


def known_room_tokens() -> set[str]:
    """Every room id and label the real building actually has.

    The output guardrail uses this to tell a real room code from an invented one.
    Agent 3 flagged that ids and plan labels differ (Lecture Theatre A is `THEATRE_A`
    but is printed as 2A.040 on the plan), so both have to count as real.
    """
    tokens: set[str] = set()
    summary = get_building_summary()
    for room in summary.get("rooms", []):
        for key in ("id", "label"):
            value = str(room.get(key, "")).strip()
            if value:
                tokens.add(value.upper())
    return tokens


def floor_of(node_id: str) -> int | None:
    summary = get_building_summary()
    for group in ("rooms", "entrances"):
        for item in summary.get(group, []):
            if item.get("id") == node_id:
                floor = item.get("floor")
                return int(floor) if isinstance(floor, (int, float)) else None
    return None
