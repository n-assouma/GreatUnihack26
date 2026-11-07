import { useState } from 'react'
import type { ClassInfo } from '../types'

interface Props { nextClass: ClassInfo | null; demoTime: string | null }

const DAY = 24 * 60 * 60 * 1000
const hhmm = (d: Date) => d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString()
const long = (d: Date) => d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

export function CalendarPage({ nextClass, demoTime }: Props) {
  // "Today" is the demo clock when demo mode sets one, otherwise the real date.
  const [today] = useState(() => new Date(demoTime ?? Date.now()))
  const [selected, setSelected] = useState(today)
  const [weekOffset, setWeekOffset] = useState(0)

  const monday = new Date(today)
  monday.setHours(0, 0, 0, 0)
  monday.setTime(monday.getTime() - ((today.getDay() + 6) % 7) * DAY + weekOffset * 7 * DAY)
  const days = Array.from({ length: 7 }, (_, i) => new Date(monday.getTime() + i * DAY))

  const start = nextClass ? new Date(nextClass.start) : null
  const end = nextClass ? new Date(nextClass.end) : null
  const classToday = nextClass && start && end && sameDay(start, selected) ? { nextClass, start, end } : null

  return (
    <main className="page calendar">
      <header className="page-head">
        <h1>Calendar</h1>
        <p className="muted">{long(selected)}</p>
      </header>

      <div className="week-nav">
        <button onClick={() => setWeekOffset((w) => w - 1)} aria-label="Previous week">Previous</button>
        <button onClick={() => { setWeekOffset(0); setSelected(today) }} disabled={weekOffset === 0 && sameDay(selected, today)}>Today</button>
        <button onClick={() => setWeekOffset((w) => w + 1)} aria-label="Next week">Next</button>
      </div>

      <ol className="week" aria-label="Choose a day">
        {days.map((d) => (
          <li key={d.toISOString()}>
            <button
              className="day" onClick={() => setSelected(d)}
              aria-pressed={sameDay(d, selected)} aria-label={long(d) + (start && sameDay(d, start) ? ', has a class' : '')}
              data-today={sameDay(d, today) || undefined}
            >
              <span className="small">{d.toLocaleDateString('en-GB', { weekday: 'short' })}</span>
              <strong>{d.getDate()}</strong>
              <span className="dot" data-on={(start && sameDay(d, start)) || undefined} />
            </button>
          </li>
        ))}
      </ol>

      <h2>{sameDay(selected, today) ? 'Today' : long(selected)}</h2>
      {classToday ? (
        <article className="card class-card">
          <div className="class-time">
            <strong>{hhmm(classToday.start)}</strong>
            <span className="muted small">{hhmm(classToday.end)}</span>
          </div>
          <div>
            <strong>{classToday.nextClass.title}</strong>
            <p className="muted">{classToday.nextClass.room_label}</p>
          </div>
        </article>
      ) : (
        <p className="card muted">No classes found for this day.</p>
      )}
    </main>
  )
}
