import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import * as api from '../api'
import type { BuildingSummary, FloorSegment, IndoorRoute } from '../types'

interface View { x: number; y: number; k: number }

const MAX_K = 8
const FIT_PADDING_PX = 90   // image pixels of context kept around the route when auto-zooming
const MIN_FIT_PX = 300      // never zoom in tighter than this many image pixels

interface PlanViewProps {
  segment: FloorSegment
  width: number
  height: number
  here: [number, number] | null
  interactive: boolean
  label: string
}

/** The floor image with the route drawn on top. Auto-fits to the route; pinch, drag and wheel when interactive. */
function PlanView({ segment, width, height, here, interactive, label }: PlanViewProps) {
  const box = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 0, h: 0 })
  const [view, setView] = useState<View>({ x: 0, y: 0, k: 1 })
  const pointers = useRef(new Map<number, { x: number; y: number }>())
  const lastPinch = useRef<number | null>(null)

  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    const measure = () => setSize({ w: el.clientWidth, h: el.clientHeight })
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const minK = size.w ? Math.min(size.w / width, size.h / height) : 1

  const clampView = useCallback((v: View): View => {
    const k = Math.min(Math.max(v.k, minK * 0.9), MAX_K)
    const margin = 60 // always leave some of the plan on screen
    return {
      k,
      x: Math.min(Math.max(v.x, margin - width * k), size.w - margin),
      y: Math.min(Math.max(v.y, margin - height * k), size.h - margin),
    }
  }, [minK, size, width, height])

  const fit = useCallback(() => {
    if (!size.w) return
    const xs = segment.points.map((p) => p[0])
    const ys = segment.points.map((p) => p[1])
    const x0 = Math.min(...xs) - FIT_PADDING_PX, x1 = Math.max(...xs) + FIT_PADDING_PX
    const y0 = Math.min(...ys) - FIT_PADDING_PX, y1 = Math.max(...ys) + FIT_PADDING_PX
    const bw = Math.max(x1 - x0, MIN_FIT_PX), bh = Math.max(y1 - y0, MIN_FIT_PX)
    const k = Math.min(Math.max(Math.min(size.w / bw, size.h / bh), minK), MAX_K)
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2
    setView(clampView({ k, x: size.w / 2 - cx * k, y: size.h / 2 - cy * k }))
  }, [segment, size, minK, clampView])

  // Re-fit when the route / floor changes or the box is resized.
  useEffect(() => { fit() }, [fit])

  const zoomAt = useCallback((cx: number, cy: number, factor: number) => {
    setView((v) => {
      const k = Math.min(Math.max(v.k * factor, minK * 0.9), MAX_K)
      const f = k / v.k
      return clampView({ k, x: cx - (cx - v.x) * f, y: cy - (cy - v.y) * f })
    })
  }, [minK, clampView])

  // Wheel zoom needs a non-passive native listener so the page does not scroll underneath.
  useEffect(() => {
    const el = box.current
    if (!el || !interactive) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const r = el.getBoundingClientRect()
      zoomAt(e.clientX - r.left, e.clientY - r.top, Math.exp(-e.deltaY * 0.0015))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [interactive, zoomAt])

  function onPointerDown(e: React.PointerEvent) {
    if (!interactive) return
    box.current?.setPointerCapture(e.pointerId)
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()]
      lastPinch.current = Math.hypot(a.x - b.x, a.y - b.y)
    }
  }

  function onPointerMove(e: React.PointerEvent) {
    const prev = pointers.current.get(e.pointerId)
    if (!interactive || !prev) return
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pointers.current.size === 1) {
      const dx = e.clientX - prev.x, dy = e.clientY - prev.y
      setView((v) => clampView({ ...v, x: v.x + dx, y: v.y + dy }))
    } else if (pointers.current.size === 2 && lastPinch.current) {
      const [a, b] = [...pointers.current.values()]
      const d = Math.hypot(a.x - b.x, a.y - b.y)
      const r = box.current!.getBoundingClientRect()
      zoomAt((a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top, d / lastPinch.current)
      lastPinch.current = d
    }
  }

  function onPointerUp(e: React.PointerEvent) {
    pointers.current.delete(e.pointerId)
    if (pointers.current.size < 2) lastPinch.current = null
  }

  const px = 1 / view.k // keep markers a constant on-screen size whatever the zoom
  const line = segment.points.map((p) => p.join(',')).join(' ')
  const first = segment.points[0], last = segment.points.at(-1)!

  return (
    <div
      ref={box} className={`plan-view${interactive ? ' interactive' : ''}`} role="img" aria-label={label}
      onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}
    >
      <div className="plan-canvas" style={{ width, height, transform: `translate(${view.x}px, ${view.y}px) scale(${view.k})` }}>
        <img src={segment.image_url} alt="" width={width} height={height} draggable={false} />
        <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} aria-hidden="true">
          <polyline points={line} className="route-casing" style={{ strokeWidth: 9 * px }} />
          <polyline points={line} className="route-line" style={{ strokeWidth: 5 * px, strokeDasharray: `${14 * px} ${9 * px}` }} />
          <circle cx={first[0]} cy={first[1]} r={11 * px} className="marker-start" style={{ strokeWidth: 3 * px }} />
          <circle cx={last[0]} cy={last[1]} r={11 * px} className="marker-end" style={{ strokeWidth: 3 * px }} />
          {here && <circle cx={here[0]} cy={here[1]} r={9 * px} className="marker-here" style={{ strokeWidth: 3 * px }} />}
        </svg>
      </div>
      {interactive && (
        <div className="plan-controls">
          <button aria-label="Zoom in" onClick={() => zoomAt(size.w / 2, size.h / 2, 1.5)}>+</button>
          <button aria-label="Zoom out" onClick={() => zoomAt(size.w / 2, size.h / 2, 1 / 1.5)}>−</button>
          <button onClick={fit}>Fit route</button>
        </div>
      )}
    </div>
  )
}

interface Props { route: IndoorRoute; step: number; onStep: (i: number) => void }

export function FloorPlanPanel({ route, step, onStep }: Props) {
  const [building, setBuilding] = useState<BuildingSummary | null>(null)
  const [floor, setFloor] = useState<number | null>(null)
  const [open, setOpen] = useState(false)
  const opener = useRef<HTMLElement | null>(null)
  const modal = useRef<HTMLDivElement>(null)

  // Remember the button that was pressed: scripted and Safari clicks do not move document.activeElement.
  function openModal(e: React.MouseEvent<HTMLElement>) { opener.current = e.currentTarget; setOpen(true) }
  function closeModal() { setOpen(false); opener.current?.focus() }

  useEffect(() => { void api.getBuilding().then(setBuilding) }, [])

  // Follow the floor of the current step; the user can still pick another tab afterwards.
  // Pass-through floors are not in segments, so fall back to the nearest floor that is drawn.
  const stepFloor = route.steps[step]?.floor
  useEffect(() => {
    if (stepFloor == null) return
    const floors = route.segments.map((s) => s.floor)
    const nearest = floors.reduce((best, f) => (Math.abs(f - stepFloor) < Math.abs(best - stepFloor) ? f : best), floors[0])
    setFloor(floors.includes(stepFloor) ? stepFloor : nearest)
  }, [stepFloor, route.segments])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeModal() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const segment = route.segments.find((s) => s.floor === floor)
  const info = building?.floors.find((f) => f.floor === floor)
  const floorLabel = (f: number) => building?.floors.find((x) => x.floor === f)?.label ?? `Floor ${f}`

  let here: [number, number] | null = null
  if (segment) {
    const i = segment.step_indices.indexOf(step)
    if (i >= 0) here = segment.points[Math.min(i, segment.points.length - 1)]
  }

  const tabs = (
    <div className="panel-tabs" role="tablist" aria-label="Floors">
      {route.segments.map((s) => (
        <button key={s.floor} role="tab" aria-selected={s.floor === floor} onClick={() => setFloor(s.floor)}>
          {floorLabel(s.floor)}
        </button>
      ))}
    </div>
  )

  const view = (interactive: boolean) =>
    segment && info ? (
      <PlanView
        segment={segment} width={info.width} height={info.height} here={here} interactive={interactive}
        label={`${info.label} floor plan with your route`}
      />
    ) : (
      <p className="panel-empty">{building ? 'No route on this floor.' : 'Loading floor plan…'}</p>
    )

  const current = route.steps[step]

  // Keep Tab inside the full-screen view while it is open.
  function trapTab(e: React.KeyboardEvent) {
    if (e.key !== 'Tab' || !modal.current) return
    const items = [...modal.current.querySelectorAll<HTMLElement>('button:not(:disabled)')]
    if (items.length === 0) return
    const first = items[0], last = items[items.length - 1]
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
  }

  return (
    <>
      <section className="floorplan">
        <div className="plan-inline">
          {view(false)}
          <button className="plan-open" onClick={openModal} aria-label="Open larger floor plan" />
          <div className="plan-overlay">
            {tabs}
            <button onClick={openModal}>Enlarge</button>
          </div>
        </div>
      </section>

      {open && (
        <div className="plan-modal" role="dialog" aria-modal="true" aria-label="Floor plan" ref={modal} onKeyDown={trapTab}>
          <header className="floor-head">
            {tabs}
            <button onClick={closeModal} autoFocus>Close</button>
          </header>
          <div className="plan-modal-body">{view(true)}</div>
          {current && (
            <footer className="plan-step">
              <p><strong>Step {step + 1} of {route.steps.length}</strong> · {current.instruction}</p>
              <div className="row">
                <button disabled={step === 0} onClick={() => onStep(step - 1)}>Back</button>
                <button disabled={step === route.steps.length - 1} onClick={() => onStep(step + 1)}>Next step</button>
              </div>
            </footer>
          )}
        </div>
      )}
    </>
  )
}
