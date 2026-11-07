import { useEffect, useState } from 'react'
import * as api from '../api'
import type { BuildingSummary, IndoorRoute } from '../types'

interface Props { route: IndoorRoute; step: number }

export function FloorPlanPanel({ route, step }: Props) {
  const [building, setBuilding] = useState<BuildingSummary | null>(null)
  const [floor, setFloor] = useState<number | null>(null)

  useEffect(() => { void api.getBuilding().then(setBuilding) }, [])

  // Follow the floor of the current step; the user can still pick another tab afterwards.
  const stepFloor = route.steps[step]?.floor
  useEffect(() => { if (stepFloor != null) setFloor(stepFloor) }, [stepFloor])

  const segment = route.segments.find((s) => s.floor === floor)
  const info = building?.floors.find((f) => f.floor === floor)
  const floorsOnRoute = route.segments.map((s) => s.floor)

  // "You are here": last point of the segment up to the current step, approximated by segment progress.
  let here: [number, number] | null = null
  if (segment) {
    const inSeg = segment.step_indices.indexOf(step)
    if (inSeg >= 0) here = segment.points[Math.min(inSeg, segment.points.length - 1)]
  }

  return (
    <section className="floorplan">
      <div className="panel-tabs" role="tablist" aria-label="Floors">
        {floorsOnRoute.map((f) => (
          <button key={f} role="tab" aria-selected={f === floor} onClick={() => setFloor(f)}>
            {building?.floors.find((x) => x.floor === f)?.label ?? `Floor ${f}`}
          </button>
        ))}
      </div>
      {segment && info ? (
        <div className="plan" style={{ aspectRatio: `${info.width} / ${info.height}` }}>
          <img src={segment.image_url} alt={`${info.label} floor plan`} />
          <svg viewBox={`0 0 ${info.width} ${info.height}`} aria-hidden="true">
            <polyline points={segment.points.map((p) => p.join(',')).join(' ')} className="route-line" />
            <circle cx={segment.points[0][0]} cy={segment.points[0][1]} r="12" className="marker-start" />
            <circle cx={segment.points.at(-1)![0]} cy={segment.points.at(-1)![1]} r="12" className="marker-end" />
            {here && <circle cx={here[0]} cy={here[1]} r="10" className="marker-here" />}
          </svg>
        </div>
      ) : (
        <p className="panel-empty">No route on this floor.</p>
      )}
    </section>
  )
}
