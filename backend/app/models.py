"""Pydantic models = docs/CONTRACTS.md §2 shared types.

Shapes here are the contract with Agent 1 (frontend) and Agent 3 (indoor engine).
Do not change a field name without agreement on the board + a human edit to CONTRACTS.

Models that carry Agent 3's data (IndoorStep, IndoorRoute, FloorSegment) are
deliberately permissive (extra keys allowed, every nullable field defaulted) so a
small difference in their payload can never 500 a response mid-demo.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# --- shared constants (CONTRACTS §1) ---
BUILDING_ID = "nancy_rothwell"
BUILDING_NAME = "Nancy Rothwell Building"
BUILDING_LAT = 53.469093
BUILDING_LNG = -2.234591
GEOFENCE_RADIUS_M = 120

Phase = Literal["idle", "outdoor", "indoor", "arrived", "escalated"]
AgentName = Literal["coordinator", "journey", "indoor"]
TransportMode = Literal["walk", "run", "bus"]


class Accessibility(BaseModel):
    no_stairs: bool = False
    visual_impairment: bool = False


class ClientContext(BaseModel):
    lat: float | None = None
    lng: float | None = None
    heading: float | None = None  # compass, null if unavailable
    demo_time: str | None = None  # overrides "now" when set
    accessibility: Accessibility = Field(default_factory=Accessibility)
    transport_pref: TransportMode | None = None
    current_step: int | None = None  # index of the indoor step the user is on


class ClassInfo(BaseModel):
    title: str
    start: str
    end: str
    building_id: str
    room_id: str
    room_label: str


class OutdoorLeg(BaseModel):
    mode: Literal["WALK", "BUS", "TRAM", "TRAIN"]
    instruction: str
    duration_min: float
    line: str | None = None
    from_stop: str | None = None
    to_stop: str | None = None
    depart_at: str | None = None
    arrive_at: str | None = None


class OutdoorRoute(BaseModel):
    mode: TransportMode
    leave_at: str
    arrive_at: str
    class_start: str
    status: Literal["on_time", "hurry", "late"]  # hurry = less than 5 min spare
    minutes_spare: float  # negative when late
    summary: str
    legs: list[OutdoorLeg] = Field(default_factory=list)
    polyline: str = ""  # Google encoded polyline


class IndoorStep(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int
    instruction: str
    floor: int
    from_node: str
    to_node: str
    distance_m: float = 0.0
    bearing_deg: float | None = None  # null for lift/stairs
    turn: str = "straight"  # start|straight|slight_*|left|right|turn_around|lift|stairs|arrive
    via: Literal["lift", "stairs"] | None = None
    target_floor: int | None = None


class FloorSegment(BaseModel):
    model_config = ConfigDict(extra="allow")

    floor: int
    image_url: str
    points: list[list[float]] = Field(default_factory=list)  # pixel coords, walking order
    step_indices: list[int] = Field(default_factory=list)


class IndoorRoute(BaseModel):
    model_config = ConfigDict(extra="allow")

    start_node: str
    destination_id: str
    accessible: bool = False
    total_distance_m: float = 0.0
    steps: list[IndoorStep] = Field(default_factory=list)
    segments: list[FloorSegment] = Field(default_factory=list)


class Contact(BaseModel):
    name: str
    phone: str | None = None
    note: str | None = None


class LastKnown(BaseModel):
    lat: float | None = None
    lng: float | None = None
    node_id: str | None = None
    floor: int | None = None


class Escalation(BaseModel):
    reason: Literal["lost", "injured", "user_request", "guardrail"]
    needs_confirmation: bool = True
    message: str
    contacts: list[Contact] = Field(default_factory=list)
    last_known: LastKnown = Field(default_factory=LastKnown)


class GuardrailEvent(BaseModel):
    stage: Literal["input", "tool", "output"]
    rule: str  # e.g. "off_topic", "no_stairs_enforced", "unknown_room"
    action: Literal["blocked", "modified", "escalated"]
    message: str


class ChatUI(BaseModel):
    next_class: ClassInfo | None = None
    outdoor_route: OutdoorRoute | None = None
    indoor_route: IndoorRoute | None = None
    escalation: Escalation | None = None
    open_panel: Literal["map", "floorplan"] | None = None  # suggestion only


class ChatResponse(BaseModel):
    reply: str | None = None  # text to show and speak (null = nothing new)
    agent: AgentName = "coordinator"
    phase: Phase = "idle"
    ui: ChatUI = Field(default_factory=ChatUI)
    guardrails: list[GuardrailEvent] = Field(default_factory=list)


# --- request bodies (CONTRACTS §3) ---


class ChatRequest(BaseModel):
    session_id: str
    message: str
    context: ClientContext = Field(default_factory=ClientContext)


class TickRequest(BaseModel):
    session_id: str
    context: ClientContext = Field(default_factory=ClientContext)


class EscalationConfirmRequest(BaseModel):
    session_id: str
    confirm: bool


class TtsRequest(BaseModel):
    text: str


class SessionDebug(BaseModel):
    phase: Phase
    agent: AgentName
    next_class: ClassInfo | None = None
    profile: Accessibility
    transport_pref: TransportMode | None = None
    current_node: str | None = None
    current_step: int | None = None
    heading: float | None = None
    heading_source: str | None = None
    lost_count: int = 0


class HealthResponse(BaseModel):
    ok: bool = True
    mocks: dict[str, str]
