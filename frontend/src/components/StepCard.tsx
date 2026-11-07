import { Icon } from './Icon'
import type { CompassStatus } from '../hooks/useCompass'
import { relativeTurn } from '../lib/turn'
import type { IndoorRoute, IndoorStep } from '../types'

const ARROW: Record<IndoorStep['turn'], { rot: number; label: string }> = {
  start: { rot: 0, label: 'Start' },
  straight: { rot: 0, label: 'Straight ahead' },
  slight_left: { rot: -35, label: 'Slight left' },
  slight_right: { rot: 35, label: 'Slight right' },
  left: { rot: -90, label: 'Turn left' },
  right: { rot: 90, label: 'Turn right' },
  turn_around: { rot: 180, label: 'Turn around' },
  lift: { rot: 0, label: 'Take the lift' },
  stairs: { rot: 0, label: 'Take the stairs' },
  arrive: { rot: 0, label: 'Arrived' },
}

const COMPASS_NOTE: Record<CompassStatus, string> = {
  off: 'Compass off', waiting: 'Looking for compass…', on: 'Compass on',
  denied: 'Compass permission denied', unavailable: 'No compass on this device',
}

interface Props {
  route: IndoorRoute; index: number; onChange: (i: number) => void
  heading: number | null; compass: CompassStatus; onCompass: () => void
}

export function StepCard({ route, index, onChange, heading, compass, onCompass }: Props) {
  const step = route.steps[index]
  if (!step) return null
  const base = ARROW[step.turn]
  // With a live compass the arrow follows the phone; otherwise it uses the backend's relative turn.
  const live = step.turn === 'arrive' ? null : relativeTurn(step, heading)
  const a = live ? { rot: live.rel, label: live.label } : base
  const last = route.steps.length - 1
  return (
    <section className="step-card" aria-label="Current step">
      <p className="sr-only" aria-live="polite">Step {index + 1} of {last + 1}. {step.instruction}</p>
      <span className="arrow" style={{ transform: `rotate(${a.rot}deg)` }} aria-hidden="true"><Icon name="arrow" size={34} /></span>
      <div>
        <strong>{step.turn === 'arrive' ? 'You have arrived' : a.label}</strong>
        <p>{step.instruction}</p>
        {route.steps[index + 1] && <p className="next-up"><span>Then:</span> {route.steps[index + 1].instruction}</p>}
        <small>Step {index + 1} of {last + 1} · Floor {step.floor} · {COMPASS_NOTE[compass]}</small>
      </div>
      <div className="row">
        <button disabled={index === 0} onClick={() => onChange(index - 1)}>Back</button>
        <button disabled={index === last} onClick={() => onChange(index + 1)}>Next step</button>
        <button aria-pressed={compass === 'on' || compass === 'waiting'} onClick={onCompass}>
          {compass === 'on' || compass === 'waiting' ? 'Compass off' : 'Use compass'}
        </button>
      </div>
    </section>
  )
}
