"""Tools the agents can call: schemas (OpenAI/LiteLLM function format) + the Python
implementations behind them.

PLAN §4.1: the AI never computes a route. These tools do, by calling real code —
the timetable, Google Routes, Agent 3's graph search — and the model only chooses
which one to call and explains what came back.

Every implementation returns a plain dict that goes back to the model as the tool
result, and stores anything the UI needs on the session state, which `main.py`
copies into `ChatResponse.ui`.
"""

from __future__ import annotations

from . import indoor_api, timetable, transit
from .state import SessionState

RECEPTION_CONTACTS = [
    # D8: no invented phone numbers, ever.
    {"name": "Nancy Rothwell reception", "phone": None, "note": "Ground floor reception desk"}
]

ESCALATION_MESSAGES = {
    "lost": "It sounds like you're going in circles. Shall I let reception know you need help?",
    "injured": "I'm sorry you're hurt. Shall I ask a member of staff to come and help you?",
    "user_request": "Of course. Shall I let reception know you'd like to speak to someone?",
    "guardrail": "I think a member of staff would be better placed to help. Shall I let them know?",
}

# --- schemas ---

TOOL_SCHEMAS: dict[str, dict] = {
    "get_next_class": {
        "type": "function",
        "function": {
            "name": "get_next_class",
            "description": (
                "Look up the student's next class from their timetable: title, start and end "
                "time, building and room. Call this before talking about their class."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    "plan_outdoor_route": {
        "type": "function",
        "function": {
            "name": "plan_outdoor_route",
            "description": (
                "Work out the journey from where the student is now to the building, for one "
                "way of travelling. Returns when to leave, when they arrive, the legs of the "
                "journey and whether they are on time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["walk", "run", "bus"],
                        "description": "How the student wants to travel.",
                    }
                },
                "required": ["mode"],
            },
        },
    },
    "locate_user": {
        "type": "function",
        "function": {
            "name": "locate_user",
            "description": (
                "Turn what the student said about where they are ('I'm at the east entrance', "
                "'near the Core 3 lifts') into a place in the building. If it is unclear you "
                "get candidates back: ask the student which one, offering at most three."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The student's own words about where they are.",
                    }
                },
                "required": ["text"],
            },
        },
    },
    "set_facing": {
        "type": "function",
        "function": {
            "name": "set_facing",
            "description": (
                "Record which way the student is facing, from what they said ('I'm facing the "
                "lifts'). Use it when directions like 'left' would otherwise be ambiguous."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "What the student says they are facing.",
                    }
                },
                "required": ["text"],
            },
        },
    },
    "plan_indoor_route": {
        "type": "function",
        "function": {
            "name": "plan_indoor_route",
            "description": (
                "Work out the step-by-step route inside the building from where the student is "
                "to a room. Returns one instruction per step with the floor and any lift. "
                "Call locate_user first so you know where they are starting from."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {
                        "type": "string",
                        "description": "Place id the student is at, e.g. 'entrance_east'.",
                    },
                    "destination": {
                        "type": "string",
                        "description": (
                            "Room id to reach, e.g. 'THEATRE_A'. Leave empty for their class "
                            "room. Never invent a room code."
                        ),
                    },
                },
                "required": ["start"],
            },
        },
    },
    "escalate_to_human": {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": (
                "Offer to get a real person involved, when the student is lost, hurt, or asks "
                "for someone. This only asks them to confirm; it does not contact anyone yet."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "enum": ["lost", "injured", "user_request"],
                        "description": "Why a person is needed.",
                    }
                },
                "required": ["reason"],
            },
        },
    },
}

HANDOFF_SCHEMAS: dict[str, dict] = {
    f"transfer_to_{target}": {
        "type": "function",
        "function": {
            "name": f"transfer_to_{target}",
            "description": description,
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }
    for target, description in {
        "coordinator": (
            "Hand back to the coordinator for anything that is not the journey to the building "
            "or navigation inside it."
        ),
        "journey": (
            "Hand over to the journey specialist to plan getting to the building: walking, "
            "running or the bus, and whether the student is on time."
        ),
        "indoor": (
            "Hand over to the indoor specialist once the student is at or inside the building, "
            "to guide them to the room step by step."
        ),
    }.items()
}


def schemas_for(tool_names: list[str], handoffs: list[str]) -> list[dict]:
    schemas = [TOOL_SCHEMAS[name] for name in tool_names if name in TOOL_SCHEMAS]
    schemas += [HANDOFF_SCHEMAS[f"transfer_to_{target}"] for target in handoffs]
    return schemas


# --- implementations ---


def get_next_class(state: SessionState) -> dict:
    found = timetable.next_class(state.now())
    state.next_class = found
    if not found:
        return {"found": False, "note": "No class found in the timetable for the next week."}
    return {
        "found": True,
        "title": found["title"],
        "starts_at": timetable.local_time(found["start"]),
        "minutes_from_now": round(timetable.minutes_until(found, state.now()) or 0),
        "room_label": found["room_label"],
        "room_id": found["room_id"],
        "building_id": found["building_id"],
        "in_nancy_rothwell": found["building_id"] == "nancy_rothwell",
    }


def plan_outdoor_route(state: SessionState, mode: str) -> dict:
    if not state.next_class:
        get_next_class(state)
    if not state.next_class:
        return {"ok": False, "note": "No next class, so there is nothing to plan a route to."}
    if state.last_location is None:
        return {
            "ok": False,
            "note": "I don't know where the student is. Ask them to turn on location, or "
            "pick a location in Settings in demo mode.",
        }

    from datetime import datetime

    try:
        class_start = datetime.fromisoformat(state.next_class["start"])
    except (ValueError, KeyError):
        return {"ok": False, "note": "The class start time is unreadable."}

    state.transport_pref = mode if mode in ("walk", "run", "bus") else state.transport_pref
    route = transit.plan(mode, state.last_location, class_start, state.now())

    if route is None:
        if mode == "bus":
            return {
                "ok": False,
                "note": "I cannot check live bus times right now. Say so plainly and offer "
                "walking instead. Do not invent a bus line or a departure time.",
            }
        return {"ok": False, "note": "I could not work out that journey."}

    state.outdoor_route = route
    return {
        "ok": True,
        "mode": route["mode"],
        "summary": route["summary"],
        "leave_at": timetable.local_time(route["leave_at"]),
        "arrive_at": timetable.local_time(route["arrive_at"]),
        "minutes_spare": route["minutes_spare"],
        "status": route["status"],
        "legs": [
            {
                "mode": leg["mode"],
                "instruction": leg["instruction"],
                "duration_min": leg["duration_min"],
                "line": leg.get("line"),
                "to_stop": leg.get("to_stop"),
            }
            for leg in route["legs"]
        ],
    }


def locate_user(state: SessionState, text: str) -> dict:
    result = indoor_api.locate(text)
    node_id = result.get("node_id")
    candidates = result.get("candidates") or []

    if not node_id:
        # F6: unclear input gets a clarifying question with up to 3 options.
        state.lost_count += 1
        return {
            "found": False,
            "note": "Ask the student which of these they are at. Offer at most three, by name.",
            "candidates": [
                {"label": item.get("label"), "node_id": item.get("node_id")}
                for item in candidates[:3]
            ],
        }

    state.current_node = node_id
    floor = indoor_api.floor_of(node_id)
    if floor is not None:
        state.current_floor = floor
    if node_id.startswith("entrance_") and state.heading_source != "compass":
        # The direction you face walking in through an entrance is known (D4),
        # so the indoor engine can give real left/right turns with no compass.
        state.heading_source = "entrance"
        state.heading = None

    label = next(
        (item.get("label") for item in candidates if item.get("node_id") == node_id), node_id
    )
    return {
        "found": True,
        "node_id": node_id,
        "label": label,
        "floor": floor,
        "confidence": result.get("confidence"),
    }


def set_facing(state: SessionState, text: str) -> dict:
    if not state.current_node:
        return {"ok": False, "note": "Find out where the student is first, with locate_user."}
    bearing = indoor_api.heading_towards(state.current_node, text)
    if bearing is None:
        return {
            "ok": False,
            "note": "That landmark is not clear from here. Ask what they can see in front of them.",
        }
    state.heading = bearing
    state.heading_source = "spoken"
    return {"ok": True, "facing_deg": bearing}


def plan_indoor_route(
    state: SessionState, start: str, destination: str = "", accessible: bool = False
) -> dict:
    # F5 is enforced in code, not in the prompt. `accessible` is what the tool
    # guardrail decided; OR-ing it with the session means a no-stairs user gets an
    # accessible route even if that stage were ever bypassed.
    accessible = bool(accessible or state.no_stairs)
    heading = state.heading if state.heading_source in ("compass", "spoken") else None

    try:
        route = indoor_api.get_indoor_route(start, destination, accessible, heading)
    except indoor_api.UnknownNodeError:
        return {
            "ok": False,
            "note": f"'{start}' or '{destination}' is not a place in this building. Ask the "
            f"student where they are, in their own words.",
        }
    except indoor_api.NoRouteError:
        return {
            "ok": False,
            "note": "There is no route I can use between those two places"
            + (" without stairs." if accessible else ".")
            + " Offer to get a member of staff.",
        }
    except Exception as exc:  # noqa: BLE001 - the engine must never 500 the chat
        print(f"[tools] indoor route failed: {type(exc).__name__}: {exc}")
        return {"ok": False, "note": "I cannot check the building right now."}

    state.indoor_route = route
    if state.current_step is None:
        state.current_step = 0

    steps = route.get("steps", [])
    return {
        "ok": True,
        "accessible": route.get("accessible"),
        "total_distance_m": route.get("total_distance_m"),
        "step_count": len(steps),
        "first_step": steps[0].get("instruction") if steps else None,
        "uses_lift": any(step.get("via") == "lift" for step in steps),
        "uses_stairs": any(step.get("via") == "stairs" for step in steps),
        "floors": sorted({step.get("floor") for step in steps if step.get("floor") is not None}),
        "steps": [
            {"index": step.get("index"), "instruction": step.get("instruction"),
             "floor": step.get("floor")}
            for step in steps
        ],
    }


def escalate_to_human(state: SessionState, reason: str = "user_request") -> dict:
    if reason not in ESCALATION_MESSAGES:
        reason = "user_request"

    lat, lng = state.last_location or (None, None)
    escalation = {
        "reason": reason,
        "needs_confirmation": True,
        "message": ESCALATION_MESSAGES[reason],
        "contacts": RECEPTION_CONTACTS,
        "last_known": {
            "lat": lat,
            "lng": lng,
            "node_id": state.current_node,
            "floor": state.current_floor,
        },
    }
    state.escalation = escalation
    from .state import set_phase

    set_phase(state, "escalated")
    return {
        "ok": True,
        "asked": escalation["message"],
        "note": "Ask the student to confirm with the card shown on screen. Do not claim anyone "
        "has been contacted yet.",
    }


IMPLEMENTATIONS = {
    "get_next_class": get_next_class,
    "plan_outdoor_route": plan_outdoor_route,
    "locate_user": locate_user,
    "set_facing": set_facing,
    "plan_indoor_route": plan_indoor_route,
    "escalate_to_human": escalate_to_human,
}
