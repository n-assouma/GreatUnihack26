import { useCallback, useState } from 'react'
import type { ClientContext } from '../types'

export type LocationPreset = 'gps' | 'home' | 'east'

export interface Settings {
  no_stairs: boolean
  visual_impairment: boolean
  transport_pref: 'walk' | 'run' | 'bus' | null
  voice: boolean
  use_location: boolean
  voice_speed: number        // 1 = normal; applied when audio is played, so it works for every voice
  more_instructions: boolean // read the whole journey / the next steps, not one instruction at a time
  long_press_read: boolean   // hold a button or message to hear it read aloud
  auto_switch: boolean       // open the Map for a new bus route and the Floor plan on arrival
  high_contrast: boolean
  large_text: boolean
  demo_mode: boolean
  demo_time: string | null        // datetime-local value, e.g. "2026-11-07T08:20"
  location_preset: LocationPreset
}

export const DEFAULT_SETTINGS: Settings = {
  no_stairs: false,
  visual_impairment: false,
  transport_pref: null,
  voice: false,
  use_location: false,
  voice_speed: 1.2,
  more_instructions: true,
  long_press_read: true,
  auto_switch: true,
  high_contrast: false,
  large_text: false,
  demo_mode: false,
  demo_time: null,
  location_preset: 'gps',
}

const KEY = 'settings'

function load(): Settings {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? { ...DEFAULT_SETTINGS, ...JSON.parse(raw) } : DEFAULT_SETTINGS
  } catch {
    return DEFAULT_SETTINGS
  }
}

export function useSettings() {
  const [settings, setSettings] = useState<Settings>(load)
  const update = useCallback((patch: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch }
      try { localStorage.setItem(KEY, JSON.stringify(next)) } catch { /* private mode: keep in memory */ }
      return next
    })
  }, [])
  return [settings, update] as const
}

// Both values come from docs/CONTRACTS.md §1.
// DEMO_HOME_LAT_LNG: Ashburne Hall, Fallowfield (the team's chosen address).
// OUTSIDE_EAST_LAT_LNG is still TBD there; the contract says BUILDING_LAT_LNG works for it, because anything within
// GEOFENCE_RADIUS_M (120 m) of the building triggers indoor mode.
export const PRESET_COORDS: Record<LocationPreset, { lat: number; lng: number } | null> = {
  gps: null,
  home: { lat: 53.445273, lng: -2.215431 },
  east: { lat: 53.469093, lng: -2.234591 },
}

export function toContext(
  s: Settings, current_step: number, heading: number | null = null, position: { lat: number; lng: number } | null = null,
): ClientContext {
  // A demo preset with known coordinates wins; otherwise the live position (only if the user opted in).
  const coords = (s.demo_mode ? PRESET_COORDS[s.location_preset] : null) ?? position
  return {
    ...(coords ?? {}),
    demo_time: s.demo_mode && s.demo_time ? new Date(s.demo_time).toISOString() : null,
    accessibility: { no_stairs: s.no_stairs, visual_impairment: s.visual_impairment },
    transport_pref: s.transport_pref,
    heading,
    current_step,
  }
}
