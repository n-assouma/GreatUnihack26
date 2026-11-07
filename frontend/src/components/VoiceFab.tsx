import { Icon } from './Icon'
import { VoiceIndicator, type VoiceState } from './VoiceIndicator'

interface Props {
  state: VoiceState
  transcript: string
  listening: boolean
  error: string | null
  onToggle: () => void
  onStop: () => void
}

/**
 * Floating microphone for every screen except Chat, so you can ask the AI something without leaving the Map,
 * the Floor plan or the Calendar. While it listens / thinks / speaks, the animated strip sits next to it.
 */
export function VoiceFab({ state, transcript, listening, error, onToggle, onStop }: Props) {
  return (
    <div className="voice-float">
      {state !== 'idle' && (
        <div className="voice-float-strip"><VoiceIndicator state={state} transcript={transcript} onStop={onStop} /></div>
      )}
      {error && <p className="notice" role="alert">{error}</p>}
      <button
        className="voice-fab" aria-pressed={listening} onClick={onToggle}
        aria-label={listening ? 'Stop listening' : 'Ask the assistant by voice'}
      >
        <Icon name="mic" size={24} />
      </button>
    </div>
  )
}
