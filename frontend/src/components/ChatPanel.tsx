import { useEffect, useRef, useState } from 'react'
import type { AgentName, ClassInfo, GuardrailEvent } from '../types'

export interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  agent?: AgentName
  guardrails?: GuardrailEvent[]
}

export const MAX_INPUT_CHARS = 2000
const NEAR_BOTTOM_PX = 80

interface Props {
  messages: ChatMessage[]
  pending: boolean
  nextClass: ClassInfo | null
  suggestions: string[]
  onSend: (text: string) => void
}

export function ChatPanel({ messages, pending, nextClass, suggestions, onSend }: Props) {
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
              {m.guardrails?.map((g, j) => (
                <span key={j} className="badge" title={g.message}>Guardrail: {g.message} ({g.action})</span>
              ))}
            </div>
          ))}
          {pending && <div className="msg typing" aria-label="Assistant is replying"><span /><span /><span /></div>}
        </div>
        {showJump && <button className="jump" onClick={jumpToLatest}>Jump to latest</button>}
      </div>
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
        <button type="submit" disabled={pending || !text.trim()}>Send</button>
      </form>
    </section>
  )
}
