import { useEffect } from 'react'
import type { AgentName } from '../types'

export interface ToastMessage { id: number; text: string; agent: AgentName }

const AUTO_DISMISS_MS = 12_000

interface Props { toast: ToastMessage | null; onDismiss: () => void }

/** Banner for messages the assistant sends on its own (reminders, hurry warnings, mode switch). */
export function Toast({ toast, onDismiss }: Props) {
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(onDismiss, AUTO_DISMISS_MS)
    return () => clearTimeout(t)
  }, [toast, onDismiss])

  // The region stays mounted so screen readers pick up content changes reliably.
  return (
    <div className="toast-region" role="status" aria-live="polite">
      {toast && (
        <div className="toast">
          <div>
            <span className="agent-tag">{toast.agent}</span>
            <p>{toast.text}</p>
          </div>
          <button onClick={onDismiss} aria-label="Dismiss message">Dismiss</button>
        </div>
      )}
    </div>
  )
}
