import { Icon, type IconName } from './Icon'

export type Tab = 'chat' | 'map' | 'plan' | 'calendar' | 'settings'

const TABS: { id: Tab; icon: IconName; label: string }[] = [
  { id: 'chat', icon: 'chat', label: 'Chat' },
  { id: 'map', icon: 'map', label: 'Map' },
  { id: 'plan', icon: 'layers', label: 'Floor plan' },
  { id: 'calendar', icon: 'calendar', label: 'Calendar' },
  { id: 'settings', icon: 'settings', label: 'Settings' },
]

interface Props {
  tab: Tab
  onChange: (t: Tab) => void
  /** Tabs with something new in them (a route just arrived). Shown as a dot. */
  badges: Partial<Record<Tab, boolean>>
}

export function NavBar({ tab, onChange, badges }: Props) {
  return (
    <nav className="navbar" aria-label="Main">
      {TABS.map((t) => (
        <button key={t.id} className="nav-item" aria-current={tab === t.id ? 'page' : undefined} onClick={() => onChange(t.id)}>
          <Icon name={t.icon} />
          <span>{t.label}</span>
          {badges[t.id] && <><i className="nav-dot" aria-hidden="true" /><span className="sr-only">New</span></>}
        </button>
      ))}
    </nav>
  )
}
