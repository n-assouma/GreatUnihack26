import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { v4 as uuid } from 'uuid'
import * as api from './api'
import { CalendarPage } from './components/CalendarPage'
import { ChatPanel, type ChatMessage } from './components/ChatPanel'
import { FloorPlanPanel } from './components/FloorPlanPanel'
import { NavBar, type Tab } from './components/NavBar'
import { Settings } from './components/Settings'
import { StatusBar } from './components/StatusBar'
import { StepCard } from './components/StepCard'
import { Toast, type ToastMessage } from './components/Toast'
import { useCompass } from './hooks/useCompass'
import { useGeolocation } from './hooks/useGeolocation'
import { Welcome } from './components/Welcome'
import { PRESET_COORDS, toContext, useSettings } from './hooks/useSettings'
import type { ChatResponse } from './types'

// The map (and the Google Maps loader) is only downloaded when the Map tab is first opened.
const MapPanel = lazy(() => import('./components/MapPanel').then((m) => ({ default: m.MapPanel })))

function sessionId(): string {
  try {
    let id = localStorage.getItem('session_id')
    if (!id) { id = uuid(); localStorage.setItem('session_id', id) }
    return id
  } catch {
    return uuid()
  }
}

// Cap the in-memory history so a very long session cannot grow the DOM without bound.
const MAX_MESSAGES = 500

type View = 'welcome' | 'onboarding' | 'main'

function initialView(): View {
  try { return localStorage.getItem('onboarded') ? 'main' : 'welcome' } catch { return 'welcome' }
}

export default function App() {
  const [view, setView] = useState<View>(initialView)
  const [tab, setTab] = useState<Tab>('chat')
  const [settings, updateSettings] = useSettings()
  const [sid] = useState(sessionId)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [state, setState] = useState<ChatResponse | null>(null)
  const [step, setStep] = useState(0)
  const [pending, setPending] = useState(false)
  const [mapOpened, setMapOpened] = useState(false)
  const [toast, setToast] = useState<ToastMessage | null>(null)
  const compass = useCompass()
  const position = useGeolocation(settings.use_location)
  const [panel, setPanel] = useState<'map' | 'floorplan' | 'hide'>('hide')
  const lastSuggested = useRef<string | null>(null)

  const context = toContext(settings, step, compass.heading, position)

  // Display preferences are applied on <html> so the CSS tokens change everywhere.
  useEffect(() => {
    const root = document.documentElement
    if (settings.high_contrast) root.dataset.contrast = 'high'; else delete root.dataset.contrast
    if (settings.large_text) root.dataset.text = 'large'; else delete root.dataset.text
  }, [settings.high_contrast, settings.large_text])

  function finishSetup() {
    try { localStorage.setItem('onboarded', '1') } catch { /* ignore */ }
    setView('main')
  }

  // Merge non-null fields from a response into UI state; open the panel only when the suggestion changes.
  // fromTick: the assistant spoke on its own (reminder, hurry warning, mode switch), so also raise a toast.
  function apply(res: ChatResponse, fromTick = false) {
    setState((prev) => ({ ...res, ui: { ...prev?.ui, ...Object.fromEntries(Object.entries(res.ui).filter(([, v]) => v != null)) } }))
    if (res.ui.indoor_route) setStep(0)
    const suggestion = res.ui.open_panel ?? null
    if (suggestion && suggestion !== lastSuggested.current) setPanel(suggestion)
    lastSuggested.current = suggestion
    if (fromTick && res.reply) setToast({ id: Date.now(), text: res.reply, agent: res.agent })
    if (res.reply) setMessages((m) => [...m, { role: 'assistant' as const, text: res.reply!, agent: res.agent, guardrails: res.guardrails }].slice(-MAX_MESSAGES))
  }

  async function send(text: string) {
    setMessages((m) => [...m, { role: 'user' as const, text }].slice(-MAX_MESSAGES))
    setPending(true)
    try {
      apply(await api.chat(sid, text, context))
    } finally {
      setPending(false)
    }
  }

  async function confirm(yes: boolean) {
    apply(await api.confirmEscalation(sid, yes))
  }

  // Tick on load and whenever the demo time / location / accessibility settings change (PLAN F13).
  const tickKey = JSON.stringify([settings.demo_mode, settings.demo_time, settings.location_preset, settings.no_stairs, position && [position.lat.toFixed(4), position.lng.toFixed(4)]])
  useEffect(() => {
    if (view === 'main') void api.tick(sid, toContext(settings, 0, compass.heading, position)).then((r) => apply(r, true))
  }, [tickKey, view]) // eslint-disable-line react-hooks/exhaustive-deps

  // Poll /api/tick every 15 s (PLAN F13) using the latest settings and step, without re-creating the timer.
  const latest = useRef(context)
  latest.current = context
  useEffect(() => {
    if (view !== 'main') return
    const id = setInterval(() => { void api.tick(sid, latest.current).then((r) => apply(r, true)) }, 15_000)
    return () => clearInterval(id)
  }, [view, sid]) // eslint-disable-line react-hooks/exhaustive-deps

  if (view === 'welcome') return <Welcome onStart={() => setView('onboarding')} />
  if (view === 'onboarding') {
    return <Settings settings={settings} onChange={updateSettings} onboarding onDone={finishSetup} />
  }

  const route = state?.ui.indoor_route ?? null
  const hasOutdoor = Boolean(state?.ui.outdoor_route)
  const phase = state?.phase ?? 'idle'

  // One-tap messages that match where the student is in the journey (the demo script, PLAN §7).
  useEffect(() => { if (panel === 'map') setMapOpened(true) }, [panel])

  const suggestions =
    phase === 'indoor' || phase === 'arrived' ? ["I'm lost", 'I hurt my ankle']
    : phase === 'escalated' ? []
    : hasOutdoor ? ["I'm at the East entrance", "I've arrived", "I'm lost"]
    : state?.ui.next_class ? ["I'll take the bus", "I'll walk", 'How do I get to class?']
    : ['What is my next class?']

  // Demo presets without coordinates send no position, so the bus route cannot start anywhere.
  const presetMissing = settings.demo_mode && settings.location_preset !== 'gps' && PRESET_COORDS[settings.location_preset] === null
  const escalation = state?.ui.escalation ?? null

  return (
    <div className="shell">
      <Toast toast={toast} onDismiss={() => setToast(null)} />
      <div className="shell-body">
        {tab === 'chat' && (
          <div className="app">
            <StatusBar demo={settings.demo_mode} nextClass={state?.ui.next_class ?? null} outdoor={state?.ui.outdoor_route ?? null} phase={state?.phase ?? 'idle'} />
            {presetMissing && <p className="notice">Demo location has no coordinates yet, so no start point is sent. Pick Home or Real GPS in Settings.</p>}
            {(state?.phase === 'indoor' || state?.phase === 'arrived') && route && (
              <StepCard route={route} index={step} onChange={setStep} heading={compass.heading} compass={compass.status} onCompass={compass.status === 'on' || compass.status === 'waiting' ? compass.disable : compass.enable} />
            )}
            <div className="panel-tabs" role="tablist">
              {(['map', 'floorplan', 'hide'] as const).map((p) => (
                <button key={p} role="tab" aria-selected={panel === p} onClick={() => setPanel(p)}>
                  {p === 'map' ? 'Map' : p === 'floorplan' ? 'Floor plan' : 'Hide'}
                </button>
              ))}
            </div>
            {panel === 'floorplan' && (
              route ? <FloorPlanPanel route={route} step={step} onStep={setStep} /> : <p className="panel-empty">No indoor route yet.</p>
            )}
            {/* Once opened the map stays mounted (hidden), so switching tabs does not reload it. */}
            {mapOpened && (
              <div hidden={panel !== 'map'}>
                <Suspense fallback={<div className="skeleton" role="status" aria-label="Loading map" />}>
                  <MapPanel route={state?.ui.outdoor_route ?? null} visible={panel === 'map'} />
                </Suspense>
              </div>
            )}
            {escalation && (
              <div className="escalation" role="alert" aria-label="Contact reception">
                <p>{escalation.message}</p>
                {escalation.needs_confirmation ? (
                  <div className="row">
                    <button onClick={() => confirm(true)}>Yes</button>
                    <button onClick={() => confirm(false)}>No</button>
                  </div>
                ) : (
                  <ul>{escalation.contacts.map((c) => <li key={c.name}>{c.name}{c.note ? `: ${c.note}` : ''}</li>)}</ul>
                )}
              </div>
            )}
            <ChatPanel messages={messages} pending={pending} nextClass={state?.ui.next_class ?? null} suggestions={suggestions} onSend={send} />
          </div>
        )}
        {tab === 'calendar' && (
          <CalendarPage nextClass={state?.ui.next_class ?? null} demoTime={settings.demo_mode ? settings.demo_time : null} />
        )}
        {tab === 'settings' && (
          <Settings settings={settings} onChange={updateSettings} onboarding={false} onDone={() => setTab('chat')} />
        )}
      </div>
      <NavBar tab={tab} onChange={setTab} />
    </div>
  )
}
