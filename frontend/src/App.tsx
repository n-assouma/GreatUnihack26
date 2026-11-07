import { useEffect, useRef, useState } from 'react'
import { v4 as uuid } from 'uuid'
import * as api from './api'
import { ChatPanel, type ChatMessage } from './components/ChatPanel'
import { FloorPlanPanel } from './components/FloorPlanPanel'
import { StatusBar } from './components/StatusBar'
import { StepCard } from './components/StepCard'
import type { ChatResponse, ClientContext } from './types'

function sessionId(): string {
  try {
    let id = localStorage.getItem('session_id')
    if (!id) { id = uuid(); localStorage.setItem('session_id', id) }
    return id
  } catch {
    return uuid()
  }
}

export default function App() {
  const [sid] = useState(sessionId)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [state, setState] = useState<ChatResponse | null>(null)
  const [step, setStep] = useState(0)
  const [panel, setPanel] = useState<'map' | 'floorplan' | 'hide'>('hide')
  const lastSuggested = useRef<string | null>(null)

  const context: ClientContext = {
    accessibility: { no_stairs: false, visual_impairment: false },
    current_step: step,
  }

  // Merge non-null fields from a response into UI state; open the panel only when the suggestion changes.
  function apply(res: ChatResponse) {
    setState((prev) => ({ ...res, ui: { ...prev?.ui, ...Object.fromEntries(Object.entries(res.ui).filter(([, v]) => v != null)) } }))
    if (res.ui.indoor_route) setStep(0)
    const suggestion = res.ui.open_panel ?? null
    if (suggestion && suggestion !== lastSuggested.current) setPanel(suggestion)
    lastSuggested.current = suggestion
    if (res.reply) setMessages((m) => [...m, { role: 'assistant', text: res.reply!, agent: res.agent, guardrails: res.guardrails }])
  }

  async function send(text: string) {
    setMessages((m) => [...m, { role: 'user', text }])
    apply(await api.chat(sid, text, context))
  }

  async function confirm(yes: boolean) {
    apply(await api.confirmEscalation(sid, yes))
  }

  useEffect(() => { void api.tick(sid, context).then(apply) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const route = state?.ui.indoor_route ?? null
  const escalation = state?.ui.escalation ?? null

  return (
    <div className="app">
      <StatusBar nextClass={state?.ui.next_class ?? null} outdoor={state?.ui.outdoor_route ?? null} phase={state?.phase ?? 'idle'} />
      {state?.phase === 'indoor' && route && (
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
        route ? <FloorPlanPanel route={route} step={step} /> : <p className="panel-empty">No indoor route yet.</p>
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
      <ChatPanel messages={messages} onSend={send} />
    </div>
  )
}
