import type { ClassInfo, OutdoorRoute, Phase } from '../types'

const STATUS = {
  on_time: { icon: '✓', text: 'On time' },
  hurry: { icon: '!', text: 'Hurry' },
  late: { icon: '✕', text: 'Late' },
} as const

interface Props { nextClass: ClassInfo | null; outdoor: OutdoorRoute | null; phase: Phase }

export function StatusBar({ nextClass, outdoor, phase }: Props) {
  const status = outdoor ? STATUS[outdoor.status] : null
  const time = nextClass ? new Date(nextClass.start).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : null
  return (
    <header className="status-bar">
      <div>
        <strong>{nextClass ? nextClass.title : 'Find My Way'}</strong>
        {nextClass && <span> · {time} · {nextClass.room_label}</span>}
      </div>
      <div className="row">
        {status && <span className={`chip chip-${outdoor!.status}`}>{status.icon} {status.text}</span>}
        <span className="chip">{phase}</span>
      </div>
    </header>
  )
}
