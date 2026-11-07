import { Icon, type IconName } from './Icon'

interface Props { onStart: () => void }

const FEATURES: { icon: IconName; title: string; text: string }[] = [
  { icon: 'calendar', title: 'Knows your next class', text: 'Pulled from your timetable, with a leave-by time.' },
  { icon: 'bus', title: 'Gets you there on time', text: 'Walk, run or bus, with a heads-up if you need to hurry.' },
  { icon: 'compass', title: 'Guides you inside', text: 'Step-by-step directions through the Nancy Rothwell Building.' },
  { icon: 'access', title: 'Built for everyone', text: 'Lift-only routes and full voice control.' },
]

export function Welcome({ onStart }: Props) {
  return (
    <main className="page welcome">
      <div className="hero">
        <div className="logo"><Icon name="pin" size={36} /></div>
        <h1>Find My Way</h1>
        <p className="tagline">From your front door to the right seat in the lecture theatre.</p>
      </div>
      <ul className="features">
        {FEATURES.map((f) => (
          <li key={f.title} className="card feature">
            <span className="feature-icon"><Icon name={f.icon} /></span>
            <div>
              <strong>{f.title}</strong>
              <p>{f.text}</p>
            </div>
          </li>
        ))}
      </ul>
      <button className="btn btn-primary btn-wide" onClick={onStart}>Get started</button>
    </main>
  )
}
