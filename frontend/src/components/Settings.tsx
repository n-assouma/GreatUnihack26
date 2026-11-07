import { useEffect, useState } from 'react'
import { Icon, type IconName } from './Icon'
import { VoiceIndicator, type VoiceState } from './VoiceIndicator'
import type { LocationPreset, Settings as S } from '../hooks/useSettings'

interface Props {
  settings: S
  onChange: (patch: Partial<S>) => void
  onDone: () => void   // only used while onboarding; the nav bar handles leaving Settings
  onboarding: boolean
}

/** A suggestion the user accepts or declines. */
function Suggestion(props: {
  icon: IconName; title: string; text: string; value: boolean; onChange: (v: boolean) => void
}) {
  return (
    <div className="card suggestion">
      <span className="feature-icon"><Icon name={props.icon} /></span>
      <div className="suggestion-body">
        <strong>{props.title}</strong>
        <p>{props.text}</p>
        <div className="segmented" role="group" aria-label={props.title}>
          <button aria-pressed={props.value} onClick={() => props.onChange(true)}>Yes, please</button>
          <button aria-pressed={!props.value} onClick={() => props.onChange(false)}>No thanks</button>
        </div>
      </div>
    </div>
  )
}

/** Lets you see the voice animations before real voice is wired in. The mic level here is simulated. */
function VoicePreview() {
  const [state, setState] = useState<VoiceState>('idle')
  const [level, setLevel] = useState(0.3)

  useEffect(() => {
    if (state !== 'listening') return
    const id = setInterval(() => setLevel(0.15 + Math.random() * 0.85), 110)
    return () => clearInterval(id)
  }, [state])

  const options: { id: VoiceState; label: string }[] = [
    { id: 'idle', label: 'Off' }, { id: 'listening', label: 'Listening' },
    { id: 'thinking', label: 'Thinking' }, { id: 'speaking', label: 'Speaking' },
  ]
  return (
    <div className="card">
      <strong>Voice animations</strong>
      <p className="muted">A preview of how the app looks while it listens to you or speaks. The microphone level is simulated here.</p>
      <div className="choice-row" role="group" aria-label="Preview state">
        {options.map((o) => (
          <button key={o.id} className="choice" aria-pressed={state === o.id} onClick={() => setState(o.id)}>{o.label}</button>
        ))}
      </div>
      <div className="voice-preview">
        <VoiceIndicator state={state} level={state === 'listening' ? level : undefined} onStop={() => setState('idle')} />
      </div>
    </div>
  )
}

const TRANSPORT = [
  { id: 'walk', icon: 'walk', label: 'Walk' },
  { id: 'run', icon: 'run', label: 'Run' },
  { id: 'bus', icon: 'bus', label: 'Bus' },
] as const

const PRESETS: { id: LocationPreset; label: string }[] = [
  { id: 'gps', label: 'Real GPS' },
  { id: 'home', label: 'Home' },
  { id: 'east', label: 'Outside East entrance' },
]

export function Settings({ settings, onChange, onDone, onboarding }: Props) {
  return (
    <main className="page settings">
      <header className="page-head">
        <h1>{onboarding ? 'Make it yours' : 'Settings'}</h1>
        <p className="muted">
          {onboarding ? 'A few quick suggestions. You can change any of them later.' : 'Your preferences are saved on this device.'}
        </p>
      </header>

      <h2>Suggested for you</h2>
      <Suggestion
        icon="lift" title="Avoid stairs"
        text="Always route me by lift. Use this if you are injured, using a wheelchair, or carrying something heavy."
        value={settings.no_stairs} onChange={(v) => onChange({ no_stairs: v })}
      />
      <Suggestion
        icon="eye" title="Describe things in more detail"
        text="Longer spoken directions and replies read aloud, for blind or low-vision users."
        value={settings.visual_impairment} onChange={(v) => onChange({ visual_impairment: v })}
      />
      <Suggestion
        icon="volume" title="Read replies aloud"
        text="Hear each answer as well as see it."
        value={settings.voice} onChange={(v) => onChange({ voice: v })}
      />

      <Suggestion
        icon="pin" title="Use my location"
        text="Needed to plan your journey from where you are. It is only used while you use the app, and your browser will ask you first."
        value={settings.use_location} onChange={(v) => onChange({ use_location: v })}
      />

      <div className="card">
        <strong>How do you like to get to class?</strong>
        <p className="muted">We will suggest this first. You can always ask for something else.</p>
        <div className="choice-row" role="group" aria-label="Preferred transport">
          {TRANSPORT.map((t) => (
            <button
              key={t.id} className="choice" aria-pressed={settings.transport_pref === t.id}
              onClick={() => onChange({ transport_pref: settings.transport_pref === t.id ? null : t.id })}
            >
              <Icon name={t.icon} size={18} /> {t.label}
            </button>
          ))}
        </div>
      </div>

      <h2>Voice</h2>
      <VoicePreview />

      <h2>Display</h2>
      <Suggestion
        icon="contrast" title="High contrast"
        text="Stronger colours and borders so everything is easier to see."
        value={settings.high_contrast} onChange={(v) => onChange({ high_contrast: v })}
      />
      <Suggestion
        icon="text" title="Larger text"
        text="Make all text bigger across the app."
        value={settings.large_text} onChange={(v) => onChange({ large_text: v })}
      />

      <h2>For the demo</h2>
      <div className="card">
        <Suggestion
          icon="flask" title="Demo mode"
          text="Set a pretend time and place so the whole journey can be shown in one room."
          value={settings.demo_mode} onChange={(v) => onChange({ demo_mode: v })}
        />
        {settings.demo_mode && (
          <div className="demo-fields">
            <label>
              Pretend it is
              <input
                type="datetime-local" value={settings.demo_time ?? ''}
                onChange={(e) => onChange({ demo_time: e.target.value || null })}
              />
            </label>
            <div className="choice-row" role="group" aria-label="Pretend location">
              {PRESETS.map((p) => (
                <button
                  key={p.id} className="choice" aria-pressed={settings.location_preset === p.id}
                  onClick={() => onChange({ location_preset: p.id })}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <p className="muted small">Home is Ashburne Hall. The East entrance preset uses the building centre, which is close enough to switch to indoor mode.</p>
          </div>
        )}
      </div>

      {onboarding && (
        <div className="sticky-actions">
          <button className="btn btn-primary btn-wide" onClick={onDone}>Continue</button>
        </div>
      )}
    </main>
  )
}
