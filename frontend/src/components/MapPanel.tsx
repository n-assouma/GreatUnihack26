import { useEffect, useState } from 'react'
import { AdvancedMarker, APIProvider, Map, useMap, useMapsLibrary } from '@vis.gl/react-google-maps'
import type { OutdoorLeg, OutdoorRoute } from '../types'

const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined
// docs/CONTRACTS.md §1: BUILDING_LAT_LNG (Nancy Rothwell Building)
const BUILDING = { lat: 53.469093, lng: -2.234591 }
const ROUTE_COLOUR = '#1f6b4a'

const hhmm = (iso?: string | null) => (iso ? new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : null)

/** Draws the decoded Google polyline and fits the map to it. */
function RoutePath({ encoded }: { encoded: string }) {
  const map = useMap()
  const geometry = useMapsLibrary('geometry')

  useEffect(() => {
    if (!map || !geometry || !encoded) return
    const path = geometry.encoding.decodePath(encoded)
    if (path.length === 0) return
    const line = new google.maps.Polyline({ path, map, strokeColor: ROUTE_COLOUR, strokeWeight: 5, strokeOpacity: 0.95 })
    const bounds = new google.maps.LatLngBounds()
    path.forEach((p) => bounds.extend(p))
    bounds.extend(BUILDING)
    map.fitBounds(bounds, 32)
    return () => line.setMap(null)
  }, [map, geometry, encoded])

  return null
}

function legTitle(leg: OutdoorLeg): string {
  if (leg.mode === 'BUS' && leg.line) return `Bus ${leg.line}`
  return leg.mode.charAt(0) + leg.mode.slice(1).toLowerCase()
}

function LegList({ route }: { route: OutdoorRoute }) {
  return (
    <ol className="legs" aria-label="Journey steps">
      {route.legs.map((leg, i) => {
        const times = [hhmm(leg.depart_at), hhmm(leg.arrive_at)].filter(Boolean).join(' to ')
        const stops = [leg.from_stop, leg.to_stop].filter(Boolean).join(' to ')
        return (
          <li key={i} className="leg">
            <strong>{legTitle(leg)}</strong>
            <span className="muted"> · {Math.round(leg.duration_min)} min</span>
            <p>{leg.instruction}</p>
            {(stops || times) && <p className="muted small">{[stops, times].filter(Boolean).join(' · ')}</p>}
          </li>
        )
      })}
    </ol>
  )
}

interface Props { route: OutdoorRoute | null }

export function MapPanel({ route }: Props) {
  // Google calls window.gm_authFailure when the key is rejected (wrong referrer, API not enabled, billing).
  const [authFailed, setAuthFailed] = useState(false)
  useEffect(() => {
    (window as unknown as { gm_authFailure?: () => void }).gm_authFailure = () => setAuthFailed(true)
  }, [])

  const showMap = Boolean(API_KEY) && !authFailed

  return (
    <section className="mappanel" aria-label="Map">
      {showMap ? (
        <div className="map-box">
          <APIProvider apiKey={API_KEY!} libraries={['geometry']}>
            <Map
              defaultCenter={BUILDING} defaultZoom={15} mapId="DEMO_MAP_ID" gestureHandling="cooperative"
              disableDefaultUI zoomControl clickableIcons={false}
            >
              <AdvancedMarker position={BUILDING} title="Nancy Rothwell Building" />
              {route?.polyline && <RoutePath encoded={route.polyline} />}
            </Map>
          </APIProvider>
        </div>
      ) : (
        <p className="panel-empty">
          {API_KEY ? 'The map could not load (Google rejected the key). The steps are listed below.' : 'No map key set, so only the steps are shown.'}
        </p>
      )}
      {route ? <LegList route={route} /> : <p className="panel-empty">No journey yet. Ask how to get to your next class.</p>}
    </section>
  )
}
