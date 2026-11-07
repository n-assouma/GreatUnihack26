import { useEffect, useState } from 'react'

export interface Position { lat: number; lng: number }

/** Live browser position while `enabled`. Null when off, denied or unavailable. The app works without it. */
export function useGeolocation(enabled: boolean): Position | null {
  const [pos, setPos] = useState<Position | null>(null)

  useEffect(() => {
    if (!enabled || !('geolocation' in navigator)) return
    const id = navigator.geolocation.watchPosition(
      (p) => setPos({ lat: p.coords.latitude, lng: p.coords.longitude }),
      () => setPos(null),
      { enableHighAccuracy: true, maximumAge: 10_000, timeout: 20_000 },
    )
    return () => { navigator.geolocation.clearWatch(id); setPos(null) }
  }, [enabled])

  return enabled ? pos : null
}
