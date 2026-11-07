import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { v4 as uuid } from 'uuid'
import * as api from './api'
import { CalendarPage } from './components/CalendarPage'
import { ChatPanel, type ChatMessage } from './components/ChatPanel'
import { FloorPlanPanel } from './components/FloorPlanPanel'
import { Icon } from './components/Icon'
import { NavBar, type Tab } from './components/NavBar'
import { Settings } from './components/Settings'
import { StatusBar } from './components/StatusBar'
import { Toast, type ToastMessage } from './components/Toast'
import { VoiceFab } from './components/VoiceFab'
import type { VoiceState } from './components/VoiceIndicator'
import { Welcome } from './components/Welcome'
import { useCompass } from './hooks/useCompass'
import { useGeolocation } from './hooks/useGeolocation'
import { useSpeech } from './hooks/useSpeech'
import { indoorUpcoming, outdoorScript, stepScript } from './lib/script'
import { PRESET_COORDS, toContext, useSettings } from './hooks/useSettings'
import type { ChatResponse, IndoorRoute, OutdoorRoute, Phase } from './types'

// The map (and the Google Maps loader) is only downloaded when the Map tab is first opened.
const MapPanel = lazy(() => import('./components/MapPanel').then((m) => ({ default: m.MapPanel })))

// The backend re-sends the current routes on every 15 s tick. These keys tell a re-send apart from a new route,
// so the step the student is on, the tab dots and the chat cards only react to a route that actually changed.
const indoorKey = (r: IndoorRoute) => `${r.start_node}|${r.destination_id}|${r.accessible}|${r.steps.map((s) => s.instruction).join('/')}`
const outdoorKey = (r: OutdoorRoute) => `${r.mode}|${r.polyline}`

// What the student just said decides where to take them, even when the backend re-sends a route they already had:
// stating a position ("I'm at the East entrance", "I've arrived") means the floor plan, from the first step;
// asking for a journey ("I'll take the bus", "how do I get to class") means the map.
const SAYS_POSITION = /\b(i'?m|i am|we'?re|we are)\b.*\b(at|in|by|near|inside|outside)\b|\bentrance\b|\barrived\b|\bi'?ve (got|made it|reached)\b/i
const ASKS_JOURNEY = /\b(bus|walk|run|journey|route|get (to|there)|how (do|can|should) i get|leave)\b/i

// Left-to-right order of the tabs, so a screen change can slide in from the side it is coming from.
const TAB_ORDER: Tab[] = ['chat', 'map', 'plan', 'calendar', 'settings']

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
  const [slide, setSlide] = useState<'left' | 'right'>('right')
  const [settings, updateSettings] = useSettings()
  const [sid] = useState(sessionId)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [state, setState] = useState<ChatResponse | null>(null)
  const [step, setStep] = useState(0)
  const [pending, setPending] = useState(false)
  const [mapOpened, setMapOpened] = useState(false)
  const [newRoute, setNewRoute] = useState({ map: false, plan: false })
  const [toast, setToast] = useState<ToastMessage | null>(null)
  const compass = useCompass()
  const position = useGeolocation(settings.use_location)
  // Speech: the app only talks when asked. A question asked with the mic is answered out loud; holding a button
  // reads that button aloud; "Read everything aloud" (off by default) reads every reply and step automatically.
  const askedByVoice = useRef(false)      // the message in flight came from the microphone
  const askedOutsideChat = useRef(false)  // ...from a tab other than Chat, so the answer also needs a banner
  const readNextReply = useRef(false)     // a suggestion chip was held down: read its answer aloud
  const speech = useSpeech({
    onFinal: (text) => {
      askedByVoice.current = true
      askedOutsideChat.current = tabRef.current !== 'chat'
      void send(text)
    },
    rate: settings.voice_speed,
  })
  const voiceOn = settings.voice
  const voiceOnRef = useRef(voiceOn)
  voiceOnRef.current = voiceOn
  const speakRef = useRef(speech.speak)
  speakRef.current = speech.speak
  const moreRef = useRef(settings.more_instructions || settings.visual_impairment)
  moreRef.current = settings.more_instructions || settings.visual_impairment
  const routeForVoice = state?.ui.indoor_route ?? null
  const shellRef = useRef<HTMLDivElement>(null)
  const lastIndoor = useRef('')
  const lastSent = useRef('')  // the student's latest message, read when its reply arrives
  const lastOutdoor = useRef('')

  // apply() runs from timers, so read the current tab through a ref instead of a stale closure.
  const tabRef = useRef(tab)
  tabRef.current = tab
  const phaseRef = useRef<Phase | null>(null)
  const autoRef = useRef(settings.auto_switch)
  autoRef.current = settings.auto_switch

  // Every screen change goes through here so the new screen slides in from the correct side.
  function go(next: Tab) {
    if (next === tabRef.current) return
    setSlide(TAB_ORDER.indexOf(next) > TAB_ORDER.indexOf(tabRef.current) ? 'right' : 'left')
    setTab(next)
  }

  const context = toContext(settings, step, compass.heading, position)

  // Display preferences are applied on <html> so the CSS tokens change everywhere.
  useEffect(() => {
    const root = document.documentElement
    if (settings.high_contrast) root.dataset.contrast = 'high'; else delete root.dataset.contrast
    if (settings.large_text) root.dataset.text = 'large'; else delete root.dataset.text
  }, [settings.high_contrast, settings.large_text])

  // Opening the Map tab loads the map once; visiting a tab clears its "new route" dot.
  useEffect(() => {
    if (tab === 'map') setMapOpened(true)
    if (tab === 'map' || tab === 'plan') setNewRoute((n) => (n[tab] ? { ...n, [tab]: false } : n))
  }, [tab])

  // Hold any button (or a chat message) to hear it. The press still does its normal job when released.
  // Buttons can say what to read with data-speak; suggestion chips (data-speak-reply) read the answer they get instead.
  useEffect(() => {
    const root = shellRef.current
    if (!root || !settings.long_press_read) return
    const HOLD_MS = 550
    let timer = 0, startX = 0, startY = 0
    const clear = () => window.clearTimeout(timer)
    const down = (e: PointerEvent) => {
      if (e.button !== 0) return
      const el = (e.target as HTMLElement).closest<HTMLElement>('[data-speak], button, .msg')
      if (!el || el.closest('[data-no-speak]')) return
      startX = e.clientX; startY = e.clientY
      clear()
      timer = window.setTimeout(() => {
        navigator.vibrate?.(20)
        el.classList.add('speak-flash')
        window.setTimeout(() => el.classList.remove('speak-flash'), 400)
        if (el.dataset.speakReply !== undefined) { readNextReply.current = true; return }
        const text = el.dataset.speak || el.getAttribute('aria-label') || el.textContent?.trim()
        if (text) void speakRef.current(text)
      }, HOLD_MS)
    }
    const move = (e: PointerEvent) => { if (Math.hypot(e.clientX - startX, e.clientY - startY) > 12) clear() }
    // Phones open a menu on long press; that would get in the way of holding to listen.
    const menu = (e: Event) => { if ((e.target as HTMLElement).closest('button, .msg')) e.preventDefault() }
    root.addEventListener('pointerdown', down)
    root.addEventListener('pointermove', move)
    root.addEventListener('pointerup', clear)
    root.addEventListener('pointercancel', clear)
    root.addEventListener('contextmenu', menu)
    return () => {
      clear()
      root.removeEventListener('pointerdown', down)
      root.removeEventListener('pointermove', move)
      root.removeEventListener('pointerup', clear)
      root.removeEventListener('pointercancel', clear)
      root.removeEventListener('contextmenu', menu)
    }
  }, [settings.long_press_read, view])

  // With "Read everything aloud" on, read each new indoor step when the person moves between steps.
  useEffect(() => {
    if (!voiceOnRef.current || step === 0) return
    if (routeForVoice) void speakRef.current(stepScript(routeForVoice, step, moreRef.current))
  }, [step]) // eslint-disable-line react-hooks/exhaustive-deps

  function finishSetup() {
    try { localStorage.setItem('onboarded', '1') } catch { /* ignore */ }
    setView('main')
  }

  // Merge non-null fields from a response into UI state (routes and the class survive replies that omit them).
  // fromTick: the assistant spoke on its own (reminder, hurry warning, mode switch), so also raise a toast.
  function apply(res: ChatResponse, fromTick = false) {
    setState((prev) => {
      const ui = { ...prev?.ui, ...Object.fromEntries(Object.entries(res.ui).filter(([, v]) => v != null)) }
      // Escalation is different: the backend sends null on purpose once it is answered or no longer applies,
      // and outside the escalated phase there is nothing to ask. Never keep a stale "Shall I contact reception?".
      if ('escalation' in res.ui) ui.escalation = res.ui.escalation ?? null
      if (res.phase !== 'escalated' && !res.ui.escalation) ui.escalation = null
      return { ...res, ui }
    })
    // Only a route that changed counts as new: re-sends must not reset the step or re-announce anything.
    const i = res.ui.indoor_route && indoorKey(res.ui.indoor_route) !== lastIndoor.current ? res.ui.indoor_route : null
    const o = res.ui.outdoor_route && outdoorKey(res.ui.outdoor_route) !== lastOutdoor.current ? res.ui.outdoor_route : null
    if (res.ui.indoor_route) lastIndoor.current = indoorKey(res.ui.indoor_route)
    if (res.ui.outdoor_route) lastOutdoor.current = outdoorKey(res.ui.outdoor_route)
    const said = fromTick ? '' : lastSent.current
    const statedPosition = SAYS_POSITION.test(said)
    // A new route, or the student telling us where they are, starts the steps again from the beginning.
    if (i || (statedPosition && res.ui.indoor_route)) setStep(0)
    // A route the user is not looking at gets a dot on its tab instead of yanking them to another screen.
    if (o && tabRef.current !== 'map') setNewRoute((n) => ({ ...n, map: true }))
    if (i && tabRef.current !== 'plan') setNewRoute((n) => ({ ...n, plan: true }))
    // A new route in this reply becomes a card in the chat (and a button on the banner) that opens the right screen.
    // Once the student is inside the building the floor plan is what matters, even if the reply still carries the bus route.
    const inside = res.phase === 'indoor' || res.phase === 'arrived'
    const mapCard: ChatMessage['action'] | undefined = o
      ? { tab: 'map', title: o.summary, detail: `Leave ${new Date(o.leave_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })} · ${o.status === 'on_time' ? 'On time' : o.status === 'hurry' ? 'Hurry' : 'Running late'}`, speak: `${o.summary}. ${outdoorScript(o)}` }
      : undefined
    const planCard: ChatMessage['action'] | undefined = i
      ? { tab: 'plan', title: `Indoor route · ${i.steps.length} steps`, detail: `${Math.round(i.total_distance_m)} m${i.accessible ? ' · step-free' : ''}`, speak: stepScript(i, 0, true) }
      : undefined
    const action = fromTick ? undefined : inside ? (planCard ?? mapCard) : (mapCard ?? planCard)
    // Was this answer asked for out loud (mic) or by holding a suggestion? Then it is read aloud.
    const spokenRequest = !fromTick && (askedByVoice.current || readNextReply.current)
    const bannerForVoice = !fromTick && askedByVoice.current && askedOutsideChat.current
    if (!fromTick) { askedByVoice.current = false; askedOutsideChat.current = false; readNextReply.current = false }
    // Follow the journey: a new bus route opens the Map, arriving at the building opens the Floor plan.
    const prevPhase = phaseRef.current
    phaseRef.current = res.phase
    const justArrived = inside && prevPhase !== null && prevPhase !== 'indoor' && prevPhase !== 'arrived'
    const autoTab: Tab | null = !autoRef.current || res.phase === 'escalated' ? null
      : inside && (i || justArrived || (statedPosition && res.ui.indoor_route)) ? 'plan'
      : !inside && (o || (ASKS_JOURNEY.test(said) && res.ui.outdoor_route)) ? 'map'
      : null
    const from = tabRef.current
    const leavingChat = autoTab !== null && autoTab !== from && from === 'chat'
    if (autoTab) go(autoTab)
    // The reply is not on screen when we moved away from Chat (or it came from a tick / the floating mic): show it as a banner.
    if ((fromTick || bannerForVoice || leavingChat) && res.reply) {
      const where = autoTab ?? from
      const banner = leavingChat
        ? { label: 'Back to chat', tab: 'chat' as Tab }
        : action && action.tab !== where ? { label: action.tab === 'map' ? 'Open map' : 'Open floor plan', tab: action.tab as Tab } : undefined
      setToast({ id: Date.now(), text: res.reply, agent: res.agent, action: banner })
    }
    if (res.reply && (voiceOnRef.current || spokenRequest)) {
      // Say more than the on-screen reply: the rest of the bus journey, or the next indoor steps.
      let spoken = res.reply
      if (!fromTick && moreRef.current) {
        if (inside && i) spoken += ` ${indoorUpcoming(i, 0, 2)}`
        else if (o) spoken += ` ${outdoorScript(o)}`
      }
      void speakRef.current(spoken)
    }
    if (res.reply) setMessages((m) => [...m, { role: 'assistant' as const, text: res.reply!, agent: res.agent, guardrails: res.guardrails, action }].slice(-MAX_MESSAGES))
  }

  async function send(text: string) {
    speech.cancel() // a new message cuts off whatever is being read out
    lastSent.current = text
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

  // Every hook is above this line: returning early below must never change the number of hooks that run.
  if (view === 'welcome') return <Welcome onStart={() => setView('onboarding')} />
  if (view === 'onboarding') {
    return <Settings settings={settings} onChange={updateSettings} onboarding onDone={finishSetup} />
  }

  const indoor = state?.ui.indoor_route ?? null
  const outdoor = state?.ui.outdoor_route ?? null
  const escalation = state?.ui.escalation ?? null
  const phase = state?.phase ?? 'idle'
  const inBuilding = (phase === 'indoor' || phase === 'arrived') && indoor
  const voiceState: VoiceState = speech.listening ? 'listening' : speech.speaking ? 'speaking' : pending ? 'thinking' : 'idle'
  const onCompass = compass.status === 'on' || compass.status === 'waiting' ? compass.disable : compass.enable

  // One-tap messages that match where the student is in the journey (the demo script, PLAN §7).
  const suggestions =
    phase === 'arrived' ? []
    : phase === 'indoor' ? ["What's my next step?", 'I hurt my ankle']
    : phase === 'escalated' ? []
    : outdoor ? ["I'm at the East entrance", "I've arrived"]
    : state?.ui.next_class ? ["I'll take the bus", "I'll walk", 'How do I get to class?']
    : ['What is my next class?']

  // Demo presets without coordinates send no position, so the bus route cannot start anywhere.
  const presetMissing = settings.demo_mode && settings.location_preset !== 'gps' && PRESET_COORDS[settings.location_preset] === null

  return (
    <div className="shell" ref={shellRef}>
      <Toast toast={toast} onDismiss={() => setToast(null)} onAction={go} />
      {/* Shown above every screen so a tab switch can never hide a request for help. */}
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

      <div className={`shell-body${tab !== 'chat' && speech.supported ? ' has-fab' : ''}`} data-slide={slide}>
        {tab === 'chat' && (
          <div className="app">
            <StatusBar demo={settings.demo_mode} nextClass={state?.ui.next_class ?? null} outdoor={outdoor} phase={phase} />
            {presetMissing && <p className="notice">Demo location has no coordinates yet, so no start point is sent. Pick Home or Real GPS in Settings.</p>}
            {inBuilding ? (
              <button className="step-strip" onClick={() => go('plan')}>
                <Icon name="arrow" size={20} />
                <span className="strip-text"><strong>Step {step + 1} of {indoor.steps.length}</strong> {indoor.steps[step]?.instruction}</span>
                <span className="strip-go">Floor plan</span>
              </button>
            ) : outdoor ? (
              <button className="step-strip" onClick={() => go('map')}>
                <Icon name="bus" size={20} />
                <span className="strip-text"><strong>Journey</strong> {outdoor.summary}</span>
                <span className="strip-go">Map</span>
              </button>
            ) : null}
            <ChatPanel messages={messages} pending={pending} nextClass={state?.ui.next_class ?? null} suggestions={suggestions} onSend={send}
              onOpenTab={go}
              voice={{ state: voiceState, onStop: speech.listening ? speech.stop : speech.cancel, transcript: speech.transcript }}
              mic={{ supported: speech.supported, listening: speech.listening, error: speech.error, onToggle: speech.listening ? speech.stop : speech.start }}
            />
          </div>
        )}

        {/* Once opened the map stays mounted (hidden), so switching tabs does not reload it. */}
        {mapOpened && (
          <div className="tabpane" hidden={tab !== 'map'}>
            <Suspense fallback={<div className="app"><div className="skeleton" role="status" aria-label="Loading map" /></div>}>
              <MapPanel route={outdoor} visible={tab === 'map'} pending={pending} onAsk={send} />
            </Suspense>
          </div>
        )}

        {tab === 'plan' && (
          <FloorPlanPanel
            route={indoor} step={step} onStep={setStep} heading={compass.heading} compass={compass.status}
            onCompass={onCompass} pending={pending} onAsk={send} readMore={settings.more_instructions}
          />
        )}
        {tab === 'calendar' && (
          <CalendarPage nextClass={state?.ui.next_class ?? null} demoTime={settings.demo_mode ? settings.demo_time : null} />
        )}
        {tab === 'settings' && (
          <Settings
            settings={settings} onChange={updateSettings} onboarding={false} onDone={() => go('chat')}
            sample={{ onPlay: () => { void speech.speak('This is how I will sound. Turn left and walk about fifteen metres to the lifts.') }, engine: speech.engine }}
          />
        )}
      </div>
      {tab !== 'chat' && speech.supported && (
        <VoiceFab
          state={voiceState} transcript={speech.transcript} listening={speech.listening} error={speech.error}
          onToggle={speech.listening ? speech.stop : speech.start} onStop={speech.listening ? speech.stop : speech.cancel}
        />
      )}
      <NavBar tab={tab} onChange={go} badges={newRoute} />
    </div>
  )
}
