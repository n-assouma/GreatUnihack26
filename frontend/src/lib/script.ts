import type { IndoorRoute, OutdoorRoute } from '../types'

// Builds the longer sentences that are read aloud. The text on screen stays as the backend wrote it.

const minutesWords = (n: number) => {
  const m = Math.max(1, Math.round(n))
  return `${m} minute${m === 1 ? '' : 's'}`
}

// Say "15 m" as "15 metres" so no voice reads it as the letter m.
const speakable = (text: string) => text.replace(/(\d+(?:\.\d+)?)\s?m\b/g, (_, n: string) => `${n} ${n === '1' ? 'metre' : 'metres'}`)

const sentence = (text: string) => {
  const t = speakable(text).trim()
  return /[.!?]$/.test(t) ? t : `${t}.`
}

/** Every leg of a journey, in order: "First, walk to X, about 4 minutes. Then take the 41 from A to B, ..." */
export function outdoorScript(route: OutdoorRoute): string {
  const last = route.legs.length - 1
  return route.legs
    .map((leg, i) => {
      const lead = i === 0 ? 'First,' : i === last ? 'Finally,' : 'Then,'
      const duration = `about ${minutesWords(leg.duration_min)}`
      if (leg.mode === 'WALK') {
        const where = leg.instruction.replace(/^Walk [\d.]+ min to /i, '').trim()
        return `${lead} walk to ${where}, ${duration}.`
      }
      const route_ = [leg.from_stop && `from ${leg.from_stop}`, leg.to_stop && `to ${leg.to_stop}`].filter(Boolean).join(' ')
      return `${lead} take the ${leg.line ?? 'bus'} ${route_}, ${duration}.`.replace(/\s+,/, ',')
    })
    .join(' ')
}

/** The next few indoor instructions after `from`, so the person is not told one step at a time. */
export function indoorUpcoming(route: IndoorRoute, from: number, count = 2): string {
  const lead = ['Then,', 'After that,']
  return route.steps
    .slice(from + 1, from + 1 + count)
    .map((s, i) => (s.turn === 'arrive' ? 'Then you will have arrived.' : `${lead[i] ?? 'Then,'} ${sentence(s.instruction[0].toLowerCase() + s.instruction.slice(1))}`))
    .join(' ')
}

/** What is read when the person moves to a step: this step, and (optionally) what comes next. */
export function stepScript(route: IndoorRoute, index: number, more: boolean): string {
  const step = route.steps[index]
  if (!step) return ''
  const own = `Step ${index + 1} of ${route.steps.length}. ${sentence(step.instruction)}`
  return more ? `${own} ${indoorUpcoming(route, index, 2)}`.trim() : own
}
