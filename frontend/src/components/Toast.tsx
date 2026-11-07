import { useEffect } from 'react'
import type { AgentName } from '../types'
import type { Tab } from './NavBar'

export interface ToastMessage { id: number; text: string; agent: AgentName; action?: { label: string; tab: Tab } }

const AUTO_DISMISS_MS = 12_000

interface Props { toast: ToastMessage | null; onDismiss: () => void; onAction: (tab: Tab) => void }

/** Banner for messages the assistant sends on its own (reminders, hurry warnings, mode switch). */
export function Toast({ toast, onDismiss, onAction }: Props) {
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
          <div className="toast-buttons">
            {toast.action && <button className="toast-action" onClick={() => { onAction(toast.action!.tab); onDismiss() }}>{toast.action.label}</button>}
            <button onClick={onDismiss} aria-label="Dismiss message">Dismiss</button>
          </div>
        </div>
      )}
    </div>
  )
}
