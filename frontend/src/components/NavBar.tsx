import { Icon, type IconName } from './Icon'

export type Tab = 'chat' | 'calendar' | 'settings'

const TABS: { id: Tab; icon: IconName; label: string }[] = [
  { id: 'chat', icon: 'chat', label: 'Chat' },
  { id: 'calendar', icon: 'calendar', label: 'Calendar' },
  { id: 'settings', icon: 'settings', label: 'Settings' },
]

interface Props { tab: Tab; onChange: (t: Tab) => void }

export function NavBar({ tab, onChange }: Props) {
  return (
    <nav className="navbar" aria-label="Main">
      {TABS.map((t) => (
        <button key={t.id} className="nav-item" aria-current={tab === t.id ? 'page' : undefined} onClick={() => onChange(t.id)}>
          <Icon name={t.icon} />
          <span>{t.label}</span>
        </button>
      ))}
    </nav>
  )
}
