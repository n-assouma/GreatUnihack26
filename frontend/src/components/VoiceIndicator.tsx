import { Icon } from './Icon'

export type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking'

const LABEL: Record<Exclude<VoiceState, 'idle'>, string> = {
  listening: 'Listening…',
  thinking: 'Thinking…',
  speaking: 'Speaking…',
}

const BARS = 9
// Relative weight of each bar so the shape reads as a waveform (tallest in the middle).
const WEIGHT = [0.35, 0.55, 0.75, 0.9, 1, 0.9, 0.75, 0.55, 0.35]

interface Props {
  state: VoiceState
  /** Live microphone loudness 0..1 while listening. Omit to use the built-in idle animation. */
  level?: number
  /** Shows a Stop button (stop listening, or cut off speech). */
  onStop?: () => void
  /** What the person is saying right now; replaces the generic label while listening. */
  transcript?: string
}

/**
 * Animated status for voice: pulsing rings while listening, a waveform while speaking, bouncing dots while thinking.
 * All motion is CSS. With reduced motion the animations stop but the text label still says what is happening.
 */
export function VoiceIndicator({ state, level, onStop, transcript }: Props) {
  if (state === 'idle') return null
  const driven = state === 'listening' && level !== undefined

  return (
    <div className="voice" data-state={state} data-driven={driven || undefined}>
      <span className="voice-orb" aria-hidden="true">
        <Icon name={state === 'speaking' ? 'volume' : 'mic'} size={20} />
      </span>

      {state === 'thinking' ? (
        <span className="voice-dots" aria-hidden="true"><i /><i /><i /></span>
      ) : (
        <span className="voice-bars" aria-hidden="true">
          {Array.from({ length: BARS }, (_, i) => (
            <span
              key={i}
              style={{
                ['--i' as string]: i,
                // When driven by a real level, bar height follows it; otherwise CSS animates it.
                ...(driven ? { ['--h' as string]: Math.max(0.12, Math.min(1, level! * WEIGHT[i] * 1.4)) } : {}),
              }}
            />
          ))}
        </span>
      )}

      <span className="voice-label" role="status" aria-live="polite">{transcript || LABEL[state]}</span>

      {onStop && state !== 'thinking' && (
        <button className="voice-stop" onClick={onStop} aria-label={state === 'listening' ? 'Stop listening' : 'Stop speaking'}>
          <Icon name="stop" size={18} />
        </button>
      )}
    </div>
  )
}
