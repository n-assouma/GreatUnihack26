import { Icon } from './Icon'
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

interface Props { route: IndoorRoute; index: number; onChange: (i: number) => void }

export function StepCard({ route, index, onChange }: Props) {
  const step = route.steps[index]
  if (!step) return null
  const a = ARROW[step.turn]
  const last = route.steps.length - 1
  return (
    <section className="step-card" aria-label="Current step">
      <span className="arrow" style={{ transform: `rotate(${a.rot}deg)` }} aria-hidden="true"><Icon name="arrow" size={34} /></span>
      <div>
        <strong>{step.turn === 'arrive' ? 'You have arrived' : a.label}</strong>
        <p>{step.instruction}</p>
        <small>Step {index + 1} of {last + 1} · Floor {step.floor}</small>
      </div>
      <div className="row">
        <button disabled={index === 0} onClick={() => onChange(index - 1)}>Back</button>
        <button disabled={index === last} onClick={() => onChange(index + 1)}>Next step</button>
      </div>
    </section>
  )
}
