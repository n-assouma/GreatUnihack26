// Copied from docs/CONTRACTS.md §2 and §3. Do not change without agreement on the board.

export type Phase = "idle" | "outdoor" | "indoor" | "arrived" | "escalated";
export type AgentName = "coordinator" | "journey" | "indoor";

export interface Accessibility {
  no_stairs: boolean;          // injury / wheelchair: never route via stairs
  visual_impairment: boolean;  // more verbal detail, auto voice
}

export interface ClientContext {
  lat?: number; lng?: number;          // browser geolocation or demo preset
  heading?: number | null;             // compass, null if unavailable
  demo_time?: string | null;           // overrides "now" when set
  accessibility: Accessibility;
  transport_pref?: "walk" | "run" | "bus" | null;
  current_step?: number | null;        // index of the indoor step the user is on
}

export interface ClassInfo {
  title: string; start: string; end: string;
  building_id: string; room_id: string; room_label: string;
}

export interface OutdoorLeg {
  mode: "WALK" | "BUS" | "TRAM" | "TRAIN";
  instruction: string;
  duration_min: number;
  line?: string | null;               // e.g. "142"
  from_stop?: string | null; to_stop?: string | null;
  depart_at?: string | null; arrive_at?: string | null;
}

export interface OutdoorRoute {
  mode: "walk" | "run" | "bus";
  leave_at: string; arrive_at: string; class_start: string;
  status: "on_time" | "hurry" | "late";   // hurry = less than 5 min spare
  minutes_spare: number;                   // negative when late
  summary: string;                         // "Bus 142, 18 min, arrive 08:52"
  legs: OutdoorLeg[];
  polyline: string;                        // Google encoded polyline
}

export interface IndoorStep {
  index: number;
  instruction: string;        // "Walk 20 m to the Core 3 lifts"
  floor: number;
  from_node: string; to_node: string;
  distance_m: number;
  bearing_deg: number | null; // absolute direction of this step, null for lift/stairs
  turn: "start" | "straight" | "slight_left" | "slight_right" | "left" | "right"
      | "turn_around" | "lift" | "stairs" | "arrive";   // relative to previous step
  via?: "lift" | "stairs" | null;
  target_floor?: number | null;   // for lift/stairs steps
}

export interface FloorSegment {
  floor: number;
  image_url: string;                 // "/static/floorplans/floor_0.png"
  points: [number, number][];        // pixel coords on that image, in walking order
  step_indices: number[];            // which steps belong to this segment
}

export interface IndoorRoute {
  start_node: string; destination_id: string;
  accessible: boolean; total_distance_m: number;
  steps: IndoorStep[];
  segments: FloorSegment[];
}

export interface Escalation {
  reason: "lost" | "injured" | "user_request" | "guardrail";
  needs_confirmation: boolean;       // true = ask user "Shall I contact reception?" first
  message: string;
  contacts: { name: string; phone?: string | null; note?: string | null }[];
  last_known: { lat?: number | null; lng?: number | null; node_id?: string | null; floor?: number | null };
}

export interface GuardrailEvent {
  stage: "input" | "tool" | "output";
  rule: string;                      // e.g. "off_topic", "no_stairs_enforced", "unknown_room"
  action: "blocked" | "modified" | "escalated";
  message: string;
}

export interface ChatResponse {
  reply: string | null;              // text to show and speak (null = nothing new)
  agent: AgentName;
  phase: Phase;
  ui: {
    next_class?: ClassInfo | null;
    outdoor_route?: OutdoorRoute | null;
    indoor_route?: IndoorRoute | null;
    escalation?: Escalation | null;
    open_panel?: "map" | "floorplan" | null;   // suggestion only, user can override
  };
  guardrails: GuardrailEvent[];      // empty list if none fired
}

export interface BuildingSummary {
  building_id: string; name: string; north_offset_deg: number;
  floors: { floor: number; label: string; image_url: string; width: number; height: number; pixels_per_metre: number }[];
  entrances: { id: string; label: string; floor: number }[];
  rooms: { id: string; label: string; floor: number }[];
}

export interface LocateResult {
  node_id: string | null;            // best match, null if not confident
  confidence: number;                // 0 to 1
  candidates: { node_id: string; label: string; floor: number }[];
}

// Not in CONTRACTS yet (A2 added it, additive): GET /api/timetable?demo_time=...
export interface Timetable {
  classes: ClassInfo[]; next_class: ClassInfo | null; now: string;
}

export interface SessionInfo {
  phase: Phase; agent: AgentName; next_class: ClassInfo | null; profile: unknown;
}

export interface Health {
  ok: boolean;
  mocks: { llm: boolean; routes: boolean; tts: boolean; indoor: boolean };
}
