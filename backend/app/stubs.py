"""D7 starter stubs: contract-shaped example data so Agent 1 can build against
real JSON shapes before the agents and the building graph are ready.

PLAN §5 D7: DELETE THIS FILE at M1, when the real data lands.
"""

from .models import (
    ChatResponse,
    ChatUI,
    ClassInfo,
    Escalation,
    FloorSegment,
    GuardrailEvent,
    IndoorRoute,
    IndoorStep,
    LastKnown,
    OutdoorLeg,
    OutdoorRoute,
    Contact,
)

STUB_CLASS = ClassInfo(
    title="Example Lecture (stub)",
    start="2026-11-07T09:00:00+00:00",
    end="2026-11-07T10:00:00+00:00",
    building_id="nancy_rothwell",
    room_id="THEATRE_A",
    room_label="Lecture Theatre A",
)

STUB_OUTDOOR_ROUTE = OutdoorRoute(
    mode="bus",
    leave_at="2026-11-07T08:26:00+00:00",
    arrive_at="2026-11-07T08:52:00+00:00",
    class_start="2026-11-07T09:00:00+00:00",
    status="hurry",
    minutes_spare=4,
    summary="Bus (stub), 18 min, arrive 08:52",
    legs=[
        OutdoorLeg(mode="WALK", instruction="Walk to the bus stop (stub)", duration_min=6),
        OutdoorLeg(
            mode="BUS",
            instruction="Take the bus towards the city centre (stub)",
            duration_min=12,
            line="STUB",
            from_stop="Stub Road",
            to_stop="Oxford Road / Stub",
            depart_at="2026-11-07T08:34:00+00:00",
            arrive_at="2026-11-07T08:46:00+00:00",
        ),
        OutdoorLeg(mode="WALK", instruction="Walk to the East entrance (stub)", duration_min=6),
    ],
    polyline="",
)

# Main demo route: East entrance -> Lecture Theatre A (first floor), lift only.
STUB_INDOOR_ROUTE = IndoorRoute(
    start_node="entrance_east",
    destination_id="THEATRE_A",
    accessible=True,
    total_distance_m=62,
    steps=[
        IndoorStep(
            index=0,
            instruction="Walk straight ahead for 20 metres into the lobby (stub)",
            floor=0,
            from_node="entrance_east",
            to_node="f0_core3_lobby",
            distance_m=20,
            bearing_deg=270,
            turn="start",
        ),
        IndoorStep(
            index=1,
            instruction="Turn left to the Core 3 lifts (stub)",
            floor=0,
            from_node="f0_core3_lobby",
            to_node="f0_core3_lift",
            distance_m=12,
            bearing_deg=180,
            turn="left",
        ),
        IndoorStep(
            index=2,
            instruction="Take the lift to the first floor (stub)",
            floor=0,
            from_node="f0_core3_lift",
            to_node="f1_core3_lift",
            distance_m=0,
            bearing_deg=None,
            turn="lift",
            via="lift",
            target_floor=1,
        ),
        IndoorStep(
            index=3,
            instruction="Leave the lift and walk 25 metres along the corridor (stub)",
            floor=1,
            from_node="f1_core3_lift",
            to_node="f1_theatre_a_door",
            distance_m=25,
            bearing_deg=90,
            turn="straight",
        ),
        IndoorStep(
            index=4,
            instruction="Lecture Theatre A is on your right (stub)",
            floor=1,
            from_node="f1_theatre_a_door",
            to_node="THEATRE_A",
            distance_m=5,
            bearing_deg=90,
            turn="arrive",
        ),
    ],
    segments=[
        FloorSegment(
            floor=0,
            image_url="/static/floorplans/floor_0.png",
            points=[[1120, 410], [900, 410], [900, 520]],
            step_indices=[0, 1, 2],
        ),
        FloorSegment(
            floor=1,
            image_url="/static/floorplans/floor_1.png",
            points=[[900, 520], [700, 520], [660, 500]],
            step_indices=[3, 4],
        ),
    ],
)

STUB_ESCALATION = Escalation(
    reason="lost",
    needs_confirmation=True,
    message="It sounds like you are stuck. Shall I contact reception for you?",
    contacts=[
        Contact(
            name="Nancy Rothwell reception",
            phone=None,
            note="Ground floor reception desk",
        )
    ],
    last_known=LastKnown(lat=53.469093, lng=-2.234591, node_id="f0_core3_lobby", floor=0),
)


def stub_chat_response(message: str) -> ChatResponse:
    """Pick the stub that matches the keyword in the message, so Agent 1 can
    exercise every UI panel from the chat box alone."""
    text = message.lower()

    if any(word in text for word in ("lost", "hurt", "help", "stuck")):
        return ChatResponse(
            reply="It sounds like you are stuck. Shall I contact reception for you? (stub)",
            agent="coordinator",
            phase="escalated",
            ui=ChatUI(next_class=STUB_CLASS, escalation=STUB_ESCALATION),
            guardrails=[
                GuardrailEvent(
                    stage="input",
                    rule="lost",
                    action="escalated",
                    message="User may need a human (stub).",
                )
            ],
        )

    if any(word in text for word in ("entrance", "inside", "arrived", "theatre", "room", "floor")):
        return ChatResponse(
            reply="You are at the East entrance. Walk straight ahead, then turn left to the Core 3 lifts. (stub)",
            agent="indoor",
            phase="indoor",
            ui=ChatUI(
                next_class=STUB_CLASS,
                indoor_route=STUB_INDOOR_ROUTE,
                open_panel="floorplan",
            ),
        )

    if any(word in text for word in ("bus", "walk", "run", "travel", "get there", "journey")):
        return ChatResponse(
            reply="The bus takes about 18 minutes and you arrive at 08:52. You need to hurry. (stub)",
            agent="journey",
            phase="outdoor",
            ui=ChatUI(
                next_class=STUB_CLASS,
                outdoor_route=STUB_OUTDOOR_ROUTE,
                open_panel="map",
            ),
        )

    if "weather" in text or "pizza" in text:
        return ChatResponse(
            reply="I can only help you get to your classes on campus. (stub)",
            agent="coordinator",
            phase="idle",
            ui=ChatUI(next_class=STUB_CLASS),
            guardrails=[
                GuardrailEvent(
                    stage="input",
                    rule="off_topic",
                    action="blocked",
                    message="Off topic request refused (stub).",
                )
            ],
        )

    return ChatResponse(
        reply="Your next class is at 09:00 in Lecture Theatre A, Nancy Rothwell. How would you like to travel? (stub)",
        agent="coordinator",
        phase="idle",
        ui=ChatUI(next_class=STUB_CLASS),
    )
