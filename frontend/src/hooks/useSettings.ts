import { useCallback, useState } from 'react'
import type { ClientContext } from '../types'

export type LocationPreset = 'gps' | 'home' | 'east'

export interface Settings {
  no_stairs: boolean
  visual_impairment: boolean
  transport_pref: 'walk' | 'run' | 'bus' | null
  voice: boolean
  demo_mode: boolean
  demo_time: string | null        // datetime-local value, e.g. "2026-11-07T08:20"
  location_preset: LocationPreset
}

export const DEFAULT_SETTINGS: Settings = {
  no_stairs: false,
  visual_impairment: false,
  transport_pref: null,
  voice: false,
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

// DEMO_HOME_LAT_LNG and OUTSIDE_EAST_LAT_LNG are still TBD in docs/CONTRACTS.md §1.
// Until the humans pick them, those presets send no coordinates (we do not invent any).
export const PRESET_COORDS: Record<LocationPreset, { lat: number; lng: number } | null> = {
  gps: null,
  home: null,
  east: null,
}

export function toContext(s: Settings, current_step: number): ClientContext {
  const coords = s.demo_mode ? PRESET_COORDS[s.location_preset] : null
  return {
    ...(coords ?? {}),
    demo_time: s.demo_mode && s.demo_time ? new Date(s.demo_time).toISOString() : null,
    accessibility: { no_stairs: s.no_stairs, visual_impairment: s.visual_impairment },
    transport_pref: s.transport_pref,
    current_step,
  }
}
