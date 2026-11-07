import type { IndoorStep } from '../types'

/** Mean of compass bearings that handles the 359° / 1° wrap-around. */
export function circularMean(degrees: number[]): number {
  const x = degrees.reduce((a, d) => a + Math.cos((d * Math.PI) / 180), 0)
  const y = degrees.reduce((a, d) => a + Math.sin((d * Math.PI) / 180), 0)
  return (((Math.atan2(y, x) * 180) / Math.PI) + 360) % 360
}

/**
 * Live relative turn from the phone's heading (docs/agent-1-frontend.md).
 * Returns null when the heading or the step's absolute bearing is unknown, so the caller falls back to step.turn.
 * rel is -180..180, positive = right.
 */
export function relativeTurn(step: Pick<IndoorStep, 'bearing_deg'>, heading: number | null): { rel: number; label: string } | null {
  if (heading == null || step.bearing_deg == null) return null
  const rel = ((step.bearing_deg - heading + 540) % 360) - 180
  const a = Math.abs(rel)
  const side = rel < 0 ? 'left' : 'right'
  const label = a < 25 ? 'Straight ahead' : a < 60 ? `Slight ${side}` : a < 150 ? `Turn ${side}` : 'Turn around'
  return { rel, label }
}
