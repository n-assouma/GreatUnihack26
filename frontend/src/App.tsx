import { useEffect, useRef, useState } from 'react'
import { v4 as uuid } from 'uuid'
import * as api from './api'
import { CalendarPage } from './components/CalendarPage'
import { ChatPanel, type ChatMessage } from './components/ChatPanel'
import { FloorPlanPanel } from './components/FloorPlanPanel'
import { NavBar, type Tab } from './components/NavBar'
import { Settings } from './components/Settings'
import { StatusBar } from './components/StatusBar'
import { StepCard } from './components/StepCard'
import { Welcome } from './components/Welcome'
import { toContext, useSettings } from './hooks/useSettings'
import type { ChatResponse } from './types'

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
  const [panel, setPanel] = useState<'map' | 'floorplan' | 'hide'>('hide')
  const lastSuggested = useRef<string | null>(null)

  const context = toContext(settings, step)

  function finishSetup() {
    try { localStorage.setItem('onboarded', '1') } catch { /* ignore */ }
    setView('main')
  }

  // Merge non-null fields from a response into UI state; open the panel only when the suggestion changes.
  function apply(res: ChatResponse) {
    setState((prev) => ({ ...res, ui: { ...prev?.ui, ...Object.fromEntries(Object.entries(res.ui).filter(([, v]) => v != null)) } }))
    if (res.ui.indoor_route) setStep(0)
    const suggestion = res.ui.open_panel ?? null
    if (suggestion && suggestion !== lastSuggested.current) setPanel(suggestion)
    lastSuggested.current = suggestion
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
  const tickKey = JSON.stringify([settings.demo_mode, settings.demo_time, settings.location_preset, settings.no_stairs])
  useEffect(() => {
    if (view === 'main') void api.tick(sid, toContext(settings, 0)).then(apply)
  }, [tickKey, view]) // eslint-disable-line react-hooks/exhaustive-deps

  // Poll /api/tick every 15 s (PLAN F13) using the latest settings and step, without re-creating the timer.
  const latest = useRef(context)
  latest.current = context
  useEffect(() => {
    if (view !== 'main') return
    const id = setInterval(() => { void api.tick(sid, latest.current).then(apply) }, 15_000)
    return () => clearInterval(id)
  }, [view, sid]) // eslint-disable-line react-hooks/exhaustive-deps

  if (view === 'welcome') return <Welcome onStart={() => setView('onboarding')} />
  if (view === 'onboarding') {
    return <Settings settings={settings} onChange={updateSettings} onboarding onDone={finishSetup} />
  }

  const route = state?.ui.indoor_route ?? null
  const escalation = state?.ui.escalation ?? null

  return (
    <div className="shell">
      <div className="shell-body">
        {tab === 'chat' && (
          <div className="app">
            <StatusBar demo={settings.demo_mode} nextClass={state?.ui.next_class ?? null} outdoor={state?.ui.outdoor_route ?? null} phase={state?.phase ?? 'idle'} />
            {(state?.phase === 'indoor' || state?.phase === 'arrived') && route && (
              <StepCard route={route} index={step} onChange={setStep} />
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
            {panel === 'map' && <p className="panel-empty">Map arrives at M2.</p>}
            {escalation && (
              <div className="escalation" role="alertdialog" aria-label="Contact reception">
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
            <ChatPanel messages={messages} pending={pending} onSend={send} />
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
