import { useEffect, useRef, useState } from 'react'
import type { AgentName, ClassInfo, GuardrailEvent } from '../types'
import { Icon } from './Icon'
import { VoiceIndicator, type VoiceState } from './VoiceIndicator'

export interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  agent?: AgentName
  guardrails?: GuardrailEvent[]
  /** A card under the message that jumps to the screen showing what the assistant just planned. */
  action?: { tab: 'map' | 'plan'; title: string; detail: string }
}

export const MAX_INPUT_CHARS = 2000
const NEAR_BOTTOM_PX = 80

interface Props {
  messages: ChatMessage[]
  pending: boolean
  nextClass: ClassInfo | null
  suggestions: string[]
  onSend: (text: string) => void
  /** Drives the voice animation. Pass the state from the speech hook once voice is wired. */
  voice?: { state: VoiceState; level?: number; onStop?: () => void; transcript?: string }
  /** Microphone input. Hidden when the browser has no speech recognition. */
  mic?: { supported: boolean; listening: boolean; error: string | null; onToggle: () => void }
  onOpenTab: (tab: 'map' | 'plan') => void
}

export function ChatPanel({ messages, pending, nextClass, suggestions, onSend, voice, mic, onOpenTab }: Props) {
  const [text, setText] = useState('')
  const [showJump, setShowJump] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)
  const stickToBottom = useRef(true)

  function onScroll() {
    const el = listRef.current
    if (!el) return
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX
    stickToBottom.current = near
    setShowJump(!near)
  }

  function jumpToLatest() {
    const el = listRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }

  // Follow new messages only if the reader is already at the bottom, or they just sent one.
  // Someone reading older messages is never yanked away.
  useEffect(() => {
    const el = listRef.current
    if (!el) return
    const justSent = messages.at(-1)?.role === 'user'
    if (stickToBottom.current || justSent) el.scrollTop = el.scrollHeight
  }, [messages, pending])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const t = text.trim()
    if (!t || pending) return
    setText('')
    stickToBottom.current = true
    onSend(t)
  }

  return (
    <section className="chat">
      <div className="messages-wrap">
        <div className="messages" ref={listRef} onScroll={onScroll} role="log" aria-live="polite" aria-label="Conversation">
          {messages.length === 0 && (nextClass ? (
            <div className="card chat-intro">
              <span className="agent-tag">Next class</span>
              <strong>{nextClass.title}</strong>
              <p className="muted">
                {new Date(nextClass.start).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })} · {nextClass.room_label}
              </p>
              <p>How are you getting there? Tap an option below, or ask me anything.</p>
            </div>
          ) : (
            <p className="chat-empty">Ask about your next class, your route, or where to go inside the building.</p>
          ))}
          {messages.map((m, i) => (
            <div key={i} className={`msg msg-${m.role}`}>
              {m.agent && <span className="agent-tag">{m.agent}</span>}
              <p>{m.text}</p>
              {m.action && (
                <button className="msg-action" onClick={() => onOpenTab(m.action!.tab)}>
                  <Icon name={m.action.tab === 'map' ? 'bus' : 'layers'} size={22} />
                  <span className="msg-action-text"><strong>{m.action.title}</strong><span>{m.action.detail}</span></span>
                  <span className="msg-action-go">{m.action.tab === 'map' ? 'Open map' : 'Open floor plan'}</span>
                </button>
              )}
              {m.guardrails?.map((g, j) => (
                <span key={j} className="badge" title={g.message}>Guardrail: {g.message} ({g.action})</span>
              ))}
            </div>
          ))}
          {pending && <div className="msg typing" aria-label="Assistant is replying"><span /><span /><span /></div>}
        </div>
        {showJump && <button className="jump" onClick={jumpToLatest}>Jump to latest</button>}
      </div>
      {voice && <VoiceIndicator state={voice.state} level={voice.level} onStop={voice.onStop} transcript={voice.transcript} />}
      {mic?.error && <p className="notice" role="alert">{mic.error}</p>}
      {suggestions.length > 0 && (
        <div className="quick" role="group" aria-label="Suggested messages">
          {suggestions.map((s) => (
            <button key={s} className="quick-btn" disabled={pending} onClick={() => onSend(s)}>{s}</button>
          ))}
        </div>
      )}
      <form onSubmit={submit} className="row">
        <input
          value={text} onChange={(e) => setText(e.target.value)} maxLength={MAX_INPUT_CHARS}
          aria-label="Message" placeholder="Ask Find My Way…" autoComplete="off"
        />
        {mic?.supported && (
          <button
            type="button" className="mic-btn" aria-pressed={mic.listening}
            aria-label={mic.listening ? 'Stop listening' : 'Speak your message'} onClick={mic.onToggle}
          >
            <Icon name="mic" size={20} />
          </button>
        )}
        <button type="submit" disabled={pending || !text.trim()}>Send</button>
      </form>
    </section>
  )
}
