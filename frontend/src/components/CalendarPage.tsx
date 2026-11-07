import { useEffect, useState } from 'react'
import * as api from '../api'
import type { ClassInfo } from '../types'

interface Props { nextClass: ClassInfo | null; demoTime: string | null }

const DAY = 24 * 60 * 60 * 1000
const hhmm = (d: Date) => d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString()
const long = (d: Date) => d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

export function CalendarPage({ nextClass, demoTime }: Props) {
  const [classes, setClasses] = useState<ClassInfo[]>(nextClass ? [nextClass] : [])
  const [loaded, setLoaded] = useState(false)
  // "Today" is the backend clock (the demo clock when demo mode sets one), else the browser's.
  const [today, setToday] = useState(() => new Date(demoTime ?? Date.now()))
  const [selected, setSelected] = useState(today)
  const [weekOffset, setWeekOffset] = useState(0)

  useEffect(() => {
    let cancelled = false
    void api.getTimetable(demoTime ? new Date(demoTime).toISOString() : null).then((t) => {
      if (cancelled) return
      setClasses(t.classes)
      const now = new Date(t.now)
      setToday(now)
      // Open on the next class so there is something to see, not an empty "today".
      const upcoming = t.classes.map((c) => new Date(c.start)).filter((d) => d.getTime() >= now.getTime()).sort((a, b) => a.getTime() - b.getTime())[0]
      const target = upcoming && !t.classes.some((c) => sameDay(new Date(c.start), now)) ? upcoming : now
      const weekStart = (d: Date) => { const m = new Date(d); m.setHours(0, 0, 0, 0); return m.getTime() - ((m.getDay() + 6) % 7) * DAY }
      setSelected(target)
      setWeekOffset(Math.round((weekStart(target) - weekStart(now)) / (7 * DAY)))
      setLoaded(true)
    })
    return () => { cancelled = true }
  }, [demoTime])

  const monday = new Date(today)
  monday.setHours(0, 0, 0, 0)
  monday.setTime(monday.getTime() - ((today.getDay() + 6) % 7) * DAY + weekOffset * 7 * DAY)
  const days = Array.from({ length: 7 }, (_, i) => new Date(monday.getTime() + i * DAY))

  const onDay = (d: Date) => classes.filter((c) => sameDay(new Date(c.start), d))
  const todays = onDay(selected).sort((a, b) => a.start.localeCompare(b.start))

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
        {days.map((d) => {
          const n = onDay(d).length
          return (
            <li key={d.toISOString()}>
              <button
                className="day" onClick={() => setSelected(d)} aria-pressed={sameDay(d, selected)}
                aria-label={long(d) + (n ? `, ${n} ${n === 1 ? 'class' : 'classes'}` : '')}
                data-today={sameDay(d, today) || undefined}
              >
                <span className="small">{d.toLocaleDateString('en-GB', { weekday: 'short' })}</span>
                <strong>{d.getDate()}</strong>
                <span className="dot" data-on={n > 0 || undefined} />
              </button>
            </li>
          )
        })}
      </ol>

      <h2>{sameDay(selected, today) ? 'Today' : long(selected)}</h2>
      {todays.length > 0 ? (
        todays.map((c) => (
          <article key={c.start + c.title} className="card class-card">
            <div className="class-time">
              <strong>{hhmm(new Date(c.start))}</strong>
              <span className="muted small">{hhmm(new Date(c.end))}</span>
            </div>
            <div>
              <strong>{c.title}</strong>
              <p className="muted">{c.room_label}</p>
            </div>
          </article>
        ))
      ) : (
        <p className="card muted">{loaded ? 'No classes on this day.' : 'Loading your timetable…'}</p>
      )}
    </main>
  )
}
