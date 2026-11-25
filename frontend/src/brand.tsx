export function Leaf({ className }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 40 40" fill="none">
      <path d="M7 28C2 13 17 11 32 5c3 10 0 24-13 26-5 1-9 0-12-3Z" fill="currentColor" />
      <path d="m7 35 19-21M15 26l-.5-7M19 22l7-.5" stroke="var(--color-canvas)" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  )
}

const navPaths = {
  workspace: <><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v6c0 4 14 4 14 0V6M5 12v6c0 4 14 4 14 0v-6" /></>,
  data: <><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M4 10h16M10 4v16M4 15h16" /></>,
  pipeline: <><rect x="3" y="3" width="5" height="5" rx="1" /><rect x="16" y="9.5" width="5" height="5" rx="1" /><rect x="3" y="16" width="5" height="5" rx="1" /><path d="M5.5 8v8M5.5 12H16" /></>,
  sql: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m7 9 3 3-3 3m6 0h4" /></>,
  reports: <path d="M4 4v16h16M8 16v-4m5 4V8m5 8V5" />,
  accounts: <><circle cx="9" cy="8" r="3" /><path d="M3 20v-2a6 4 0 0 1 12 0v2M16 5a3 3 0 1 1 0 6m1 3c3 0 4 2 4 4v2" /></>,
}

export function NavIcon({ name }: { name: keyof typeof navPaths }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      {navPaths[name]}
    </svg>
  )
}
