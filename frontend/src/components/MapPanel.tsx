import { useEffect, useMemo, useState } from 'react'
import { AdvancedMarker, APIProvider, Map, useMap, useMapsLibrary } from '@vis.gl/react-google-maps'
import { Icon } from './Icon'
import type { OutdoorLeg, OutdoorRoute } from '../types'

const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined
// docs/CONTRACTS.md §1: BUILDING_LAT_LNG (Nancy Rothwell Building)
const BUILDING = { lat: 53.469093, lng: -2.234591 }
const ROUTE_COLOUR = '#1f6b4a'

const clock = (d: Date) => d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
const minutes = (n: number) => `${Math.max(1, Math.round(n))} min`

const STATUS = {
  on_time: 'On time',
  hurry: 'Hurry',
  late: 'Running late',
} as const

interface TimedLeg { leg: OutdoorLeg; start: Date; end: Date }

/**
 * Google gives each leg a duration but usually no clock times. Chain the durations from the leave time so the
 * timeline can show approximate times. The chain ends at the route's own arrive_at, so nothing is invented.
 */
function timeLegs(route: OutdoorRoute): TimedLeg[] {
  let cursor = new Date(route.leave_at).getTime()
  return route.legs.map((leg) => {
    const start = leg.depart_at ? new Date(leg.depart_at) : new Date(cursor)
    const end = leg.arrive_at ? new Date(leg.arrive_at) : new Date(start.getTime() + leg.duration_min * 60_000)
    cursor = end.getTime()
    return { leg, start, end }
  })
}

const legTitle = (leg: OutdoorLeg) =>
  leg.mode === 'WALK' ? leg.instruction.replace(/^Walk [\d.]+ min to /i, 'Walk to ') : leg.line ? `Bus ${leg.line}` : leg.instruction

function LegIcon({ leg }: { leg: OutdoorLeg }) {
  if (leg.mode === 'WALK') return <Icon name="walk" size={20} />
  return <span className="line-badge">{leg.line ?? 'Bus'}</span>
}

/** Draws the decoded Google polyline and fits the map to it. Re-fits when the screen becomes visible. */
function RoutePath({ encoded, visible }: { encoded: string; visible: boolean }) {
  const map = useMap()
  const geometry = useMapsLibrary('geometry')
  const path = useMemo(() => (geometry && encoded ? geometry.encoding.decodePath(encoded) : []), [geometry, encoded])

  // A map that was hidden (display: none) needs a resize event before it will draw tiles correctly.
  useEffect(() => {
    if (map && visible) google.maps.event.trigger(map, 'resize')
  }, [map, visible])

  useEffect(() => {
    if (!map || path.length === 0 || !visible) return
    const line = new google.maps.Polyline({ path, map, strokeColor: ROUTE_COLOUR, strokeWeight: 5, strokeOpacity: 0.95 })
    const bounds = new google.maps.LatLngBounds()
    path.forEach((p) => bounds.extend(p))
    bounds.extend(BUILDING)
    map.fitBounds(bounds, 32)
    return () => line.setMap(null)
  }, [map, path, visible])

  return null
}

function Summary({ route }: { route: OutdoorRoute }) {
  const leave = new Date(route.leave_at), arrive = new Date(route.arrive_at)
  const total = (arrive.getTime() - leave.getTime()) / 60_000
  const spare = route.minutes_spare
  const spareText = spare >= 0 ? `${Math.round(spare)} min to spare` : `${Math.round(-spare)} min late`
  return (
    <div className="journey-summary">
      <div className="stats">
        <div><span className="stat-label">Leave at</span><strong className="stat-value">{clock(leave)}</strong></div>
        <div><span className="stat-label">Journey</span><strong className="stat-value">{minutes(total)}</strong></div>
        <div><span className="stat-label">Arrive</span><strong className="stat-value">{clock(arrive)}</strong></div>
      </div>
      <p className="journey-status">
        <span className={`chip chip-${route.status}`}>{STATUS[route.status]}</span>
        <span>{spareText} · class starts {clock(new Date(route.class_start))}</span>
      </p>
    </div>
  )
}

function RouteStrip({ timed }: { timed: TimedLeg[] }) {
  return (
    <ol className="route-strip" aria-label="Journey overview">
      {timed.map(({ leg }, i) => (
        <li key={i} className="strip-item">
          <LegIcon leg={leg} />
          <span>{minutes(leg.duration_min)}</span>
        </li>
      ))}
    </ol>
  )
}

function Timeline({ timed }: { timed: TimedLeg[] }) {
  return (
    <ol className="timeline" aria-label="Journey steps">
      {timed.map(({ leg, start }, i) => {
        const stops = [leg.from_stop, leg.to_stop].filter(Boolean).join(' to ')
        const detail = leg.mode === 'WALK' ? null : leg.instruction
        return (
          <li key={i} className="tl-item">
            <span className="tl-icon"><LegIcon leg={leg} /></span>
            <div className="tl-body">
              <strong>{legTitle(leg)}</strong>
              {detail && <p>{detail}</p>}
              {stops && leg.mode !== 'WALK' && <p className="muted small">{stops}</p>}
            </div>
            <div className="tl-time">
              <strong>{minutes(leg.duration_min)}</strong>
              <span className="muted small">about {clock(start)}</span>
            </div>
          </li>
        )
      })}
    </ol>
  )
}

interface Props {
  route: OutdoorRoute | null
  visible: boolean
  pending: boolean
  onAsk: (text: string) => void
}

/** The Map screen: journey summary, the map filling the screen, and the step-by-step timeline underneath. */
export function MapPanel({ route, visible, pending, onAsk }: Props) {
  // Google calls window.gm_authFailure when the key is rejected (wrong referrer, API not enabled, billing).
  const [authFailed, setAuthFailed] = useState(false)
  useEffect(() => {
    (window as unknown as { gm_authFailure?: () => void }).gm_authFailure = () => setAuthFailed(true)
  }, [])

  const timed = useMemo(() => (route ? timeLegs(route) : []), [route])
  const showMap = Boolean(API_KEY) && !authFailed

  return (
    <section className="app mappage" aria-label="Journey map">
      {route ? (
        <>
          <Summary route={route} />
          <RouteStrip timed={timed} />
        </>
      ) : (
        <div className="empty-state card">
          <Icon name="map" size={32} />
          <strong>No journey yet</strong>
          <p className="muted">Choose how you will travel and I will plan it from where you are.</p>
          <div className="quick">
            {["I'll take the bus", "I'll walk", 'How do I get to class?'].map((s) => (
              <button key={s} className="quick-btn" data-speak-reply disabled={pending} onClick={() => onAsk(s)}>{s}</button>
            ))}
          </div>
          {pending && <p className="muted" role="status">Planning your journey…</p>}
        </div>
      )}

      {showMap ? (
        <div className="map-box">
          <APIProvider apiKey={API_KEY!} libraries={['geometry']}>
            <Map
              defaultCenter={BUILDING} defaultZoom={15} mapId="DEMO_MAP_ID" gestureHandling="greedy"
              disableDefaultUI zoomControl clickableIcons={false}
            >
              <AdvancedMarker position={BUILDING} title="Nancy Rothwell Building" />
              {route?.polyline && <RoutePath encoded={route.polyline} visible={visible} />}
            </Map>
          </APIProvider>
        </div>
      ) : (
        <p className="panel-empty">
          {API_KEY ? 'The map could not load (Google rejected the key). The steps are listed below.' : 'No map key set, so only the steps are shown.'}
        </p>
      )}

      {route && (
        <details className="steps-sheet" open={!showMap || undefined}>
          <summary>Journey steps ({timed.length})</summary>
          <Timeline timed={timed} />
        </details>
      )}
    </section>
  )
}
