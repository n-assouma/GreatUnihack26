import type { ReactNode } from 'react'

const PATHS = {
  pin: <><path d="M12 21s-7-6.2-7-11a7 7 0 0114 0c0 4.8-7 11-7 11z" /><circle cx="12" cy="10" r="2.5" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></>,
  bus: <><rect x="4" y="3" width="16" height="15" rx="2" /><path d="M4 11h16M6 18v2M18 18v2" /><circle cx="8" cy="14.5" r=".8" /><circle cx="16" cy="14.5" r=".8" /></>,
  compass: <><circle cx="12" cy="12" r="9" /><path d="M16 8l-2 6-6 2 2-6z" /></>,
  access: <><circle cx="12" cy="4.5" r="1.5" /><path d="M5 8.5h14M12 8.5v5.5M9 21l3-7 3 7" /></>,
  lift: <><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M9 10l3-3 3 3M9 14l3 3 3-3" /></>,
  volume: <><path d="M4 9v6h4l5 4V5L8 9z" /><path d="M16.5 9a4 4 0 010 6" /></>,
  eye: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></>,
  flask: <><path d="M9 3h6M10 3v6l-5 9a2 2 0 002 3h10a2 2 0 002-3l-5-9V3" /></>,
  walk: <><circle cx="13" cy="4" r="1.5" /><path d="M12 8l-2 5 3 3v5M10 13l-3 2M14 9l3 3" /></>,
  run: <><circle cx="12" cy="13" r="8" /><path d="M12 9v4l2 2M9 2h6" /></>,
  chat: <path d="M21 12a8 8 0 01-11.5 7.2L4 21l1.8-5A8 8 0 1121 12z" />,
  settings: <><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0" /><circle cx="16" cy="6" r="2" /><circle cx="10" cy="12" r="2" /><circle cx="18" cy="18" r="2" /></>,
  contrast: <><circle cx="12" cy="12" r="9" /><path d="M12 3a9 9 0 010 18z" /></>,
  text: <path d="M4 7V5h16v2M12 5v14M9 19h6" />,
  mic: <><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0014 0M12 18v3" /></>,
  stop: <rect x="6" y="6" width="12" height="12" rx="2" />,
  arrow: <path d="M12 19V5M6 11l6-6 6 6" />,
} satisfies Record<string, ReactNode>

export type IconName = keyof typeof PATHS

interface Props { name: IconName; size?: number }

/** Decorative line icon. Always pair with visible text or an aria-label on the parent. */
export function Icon({ name, size = 22 }: Props) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false"
    >
      {PATHS[name]}
    </svg>
  )
}
