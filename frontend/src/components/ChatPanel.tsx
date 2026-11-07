import { useState } from 'react'
import type { AgentName, GuardrailEvent } from '../types'

export interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  agent?: AgentName
  guardrails?: GuardrailEvent[]
}

interface Props { messages: ChatMessage[]; onSend: (text: string) => void }

export function ChatPanel({ messages, onSend }: Props) {
  const [text, setText] = useState('')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const t = text.trim()
    if (!t) return
    setText('')
    onSend(t)
  }

  return (
    <section className="chat">
      <div className="messages" aria-live="polite">
        {messages.map((m, i) => (
          <div key={i} className={`msg msg-${m.role}`}>
            {m.agent && <span className="agent-tag">{m.agent}</span>}
            <p>{m.text}</p>
            {m.guardrails?.map((g, j) => (
              <span key={j} className="badge" title={g.message}>Guardrail: {g.message} ({g.action})</span>
            ))}
          </div>
        ))}
      </div>
      <form onSubmit={submit} className="row">
        <input value={text} onChange={(e) => setText(e.target.value)} aria-label="Message" placeholder="Ask Find My Way…" />
        <button type="submit">Send</button>
      </form>
    </section>
  )
}
