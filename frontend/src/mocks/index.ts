// M0 fixtures (PLAN §5 D7). Contract-shaped, placeholder images. Replace with copies of real responses at M1.
import type { BuildingSummary, ChatResponse, ClassInfo, Escalation, IndoorRoute, OutdoorRoute } from '../types'

const nextClass: ClassInfo = {
  title: 'Example lecture',
  start: '2026-11-07T09:00:00+00:00',
  end: '2026-11-07T10:00:00+00:00',
  building_id: 'nancy_rothwell',
  room_id: 'THEATRE_A',
  room_label: 'Lecture Theatre A',
}

export const outdoorRoute: OutdoorRoute = {
  mode: 'bus',
  leave_at: '2026-11-07T08:34:00+00:00',
  arrive_at: '2026-11-07T08:52:00+00:00',
  class_start: nextClass.start,
  status: 'hurry',
  minutes_spare: 4,
  summary: 'Bus 142, 18 min, arrive 08:52',
  legs: [
    { mode: 'WALK', instruction: 'Walk to Oxford Road stop', duration_min: 4, from_stop: null, to_stop: 'Oxford Road' },
    { mode: 'BUS', instruction: 'Take bus 142', duration_min: 12, line: '142', from_stop: 'Oxford Road', to_stop: 'Rumford Street' },
    { mode: 'WALK', instruction: 'Walk to the East entrance', duration_min: 2 },
  ],
  polyline: '',
}

export const indoorRoute: IndoorRoute = {
  start_node: 'entrance_east',
  destination_id: 'THEATRE_A',
  accessible: true,
  total_distance_m: 95,
  steps: [
    { index: 0, instruction: 'Walk straight ahead to the Core 3 lifts', floor: 0, from_node: 'entrance_east', to_node: 'f0_core3_lift', distance_m: 30, bearing_deg: 270, turn: 'start' },
    { index: 1, instruction: 'Turn left and walk 10 m to the lift doors', floor: 0, from_node: 'f0_core3_lift', to_node: 'f0_core3_lift_door', distance_m: 10, bearing_deg: 180, turn: 'left' },
    { index: 2, instruction: 'Take the lift to floor 1', floor: 0, from_node: 'f0_core3_lift_door', to_node: 'f1_core3_lift', distance_m: 0, bearing_deg: null, turn: 'lift', via: 'lift', target_floor: 1 },
    { index: 3, instruction: 'Walk 40 m to Lecture Theatre A', floor: 1, from_node: 'f1_core3_lift', to_node: 'THEATRE_A', distance_m: 40, bearing_deg: 90, turn: 'right' },
    { index: 4, instruction: 'You have arrived at Lecture Theatre A', floor: 1, from_node: 'THEATRE_A', to_node: 'THEATRE_A', distance_m: 0, bearing_deg: null, turn: 'arrive' },
  ],
  segments: [
    { floor: 0, image_url: '/mock/floor_0.svg', points: [[1120, 410], [820, 410], [820, 510]], step_indices: [0, 1, 2] },
    { floor: 1, image_url: '/mock/floor_1.svg', points: [[820, 510], [820, 300], [420, 300]], step_indices: [3, 4] },
  ],
}

export const escalation: Escalation = {
  reason: 'lost',
  needs_confirmation: true,
  message: 'You seem lost. Shall I contact reception?',
  contacts: [{ name: 'Reception desk', phone: null, note: 'Ground floor. Or ask a member of staff.' }],
  last_known: { node_id: 'f0_core3_lift', floor: 0 },
}

export const buildingSummary: BuildingSummary = {
  building_id: 'nancy_rothwell',
  name: 'Nancy Rothwell Building',
  north_offset_deg: 0,
  floors: [0, 1, 2, 3].map((f) => ({
    floor: f,
    label: f === 0 ? 'Ground' : `Floor ${f}`,
    image_url: `/mock/floor_${f}.svg`,
    width: 1200,
    height: 800,
    pixels_per_metre: 8,
  })),
  entrances: [
    { id: 'entrance_east', label: 'East entrance (Rumford Street)', floor: 0 },
    { id: 'entrance_south', label: 'South entrance (Booth Street East)', floor: 0 },
    { id: 'entrance_north', label: 'North entrance', floor: 0 },
  ],
  rooms: [
    { id: 'THEATRE_A', label: 'Lecture Theatre A', floor: 1 },
    { id: '3A.041', label: '3A.041', floor: 3 },
  ],
}

const base: ChatResponse = { reply: null, agent: 'coordinator', phase: 'idle', ui: {}, guardrails: [] }

export const chatOutdoor: ChatResponse = {
  ...base,
  reply: 'Your next class is at 09:00 in Lecture Theatre A. Take bus 142 and leave now.',
  agent: 'journey',
  phase: 'outdoor',
  ui: { next_class: nextClass, outdoor_route: outdoorRoute, open_panel: 'map' },
}

export const chatIndoor: ChatResponse = {
  ...base,
  reply: 'Walk straight ahead to the Core 3 lifts, then take the lift to floor 1.',
  agent: 'indoor',
  phase: 'indoor',
  ui: { next_class: nextClass, indoor_route: indoorRoute, open_panel: 'floorplan' },
  guardrails: [{ stage: 'tool', rule: 'no_stairs_enforced', action: 'modified', message: 'Used the lift route, no stairs' }],
}

export const chatEscalation: ChatResponse = {
  ...base,
  reply: escalation.message,
  agent: 'coordinator',
  phase: 'escalated',
  ui: { escalation },
}

export const chatTick: ChatResponse = { ...base }
