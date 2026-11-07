import { useCallback, useEffect, useRef, useState } from 'react'
import { circularMean } from '../lib/turn'

export type CompassStatus = 'off' | 'waiting' | 'on' | 'denied' | 'unavailable'

const SMOOTHING_WINDOW = 5
const NO_READING_MS = 2500

type OrientationEvent = DeviceOrientationEvent & { webkitCompassHeading?: number }
type IOSOrientation = { requestPermission?: () => Promise<'granted' | 'denied'> }

/**
 * Optional phone compass. The app works fully without it (backend turns are relative to the entrance's known facing).
 * iOS: permission must be requested from a tap, then webkitCompassHeading is used.
 * Android / Chrome: deviceorientationabsolute, heading = 360 - alpha. Both need HTTPS on a real phone.
 */
export function useCompass() {
  const [enabled, setEnabled] = useState(false)
  const [status, setStatus] = useState<CompassStatus>('off')
  const [heading, setHeading] = useState<number | null>(null)
  const samples = useRef<number[]>([])
  const supported = typeof window !== 'undefined' && 'DeviceOrientationEvent' in window

  const enable = useCallback(async () => {
    if (!supported) { setStatus('unavailable'); return }
    const ios = window.DeviceOrientationEvent as unknown as IOSOrientation
    if (typeof ios.requestPermission === 'function') {
      try {
        if ((await ios.requestPermission()) !== 'granted') { setStatus('denied'); return }
      } catch {
        setStatus('denied')
        return
      }
    }
    setStatus('waiting')
    setEnabled(true)
  }, [supported])

  const disable = useCallback(() => {
    setEnabled(false)
    setHeading(null)
    setStatus('off')
  }, [])

  useEffect(() => {
    if (!enabled) return
    samples.current = []
    const onEvent = (ev: Event) => {
      const e = ev as OrientationEvent
      let h: number | null = null
      if (typeof e.webkitCompassHeading === 'number') h = e.webkitCompassHeading
      else if (e.type === 'deviceorientationabsolute' && e.alpha != null) h = (360 - e.alpha) % 360
      if (h == null || Number.isNaN(h)) return
      samples.current = [...samples.current.slice(-(SMOOTHING_WINDOW - 1)), h]
      setHeading(Math.round(circularMean(samples.current)))
      setStatus('on')
    }
    window.addEventListener('deviceorientationabsolute', onEvent, true)
    window.addEventListener('deviceorientation', onEvent, true)
    // Laptops expose the API but never fire it: say so instead of waiting forever.
    const t = setTimeout(() => setStatus((s) => (s === 'waiting' ? 'unavailable' : s)), NO_READING_MS)
    return () => {
      window.removeEventListener('deviceorientationabsolute', onEvent, true)
      window.removeEventListener('deviceorientation', onEvent, true)
      clearTimeout(t)
    }
  }, [enabled])

  return { heading, status, supported, enable, disable }
}
