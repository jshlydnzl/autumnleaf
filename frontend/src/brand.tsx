export function Leaf({ className }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 40 40" fill="none">
      <path d="M7 28C2 13 17 11 32 5c3 10 0 24-13 26-5 1-9 0-12-3Z" fill="currentColor" />
      <path d="m7 35 19-21M15 26l-.5-7M19 22l7-.5" stroke="var(--color-canvas)" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  )
}

export function NavIcon({ name }: { name: 'workspace' | 'accounts' }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      {name === 'workspace'
        ? <><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v6c0 4 14 4 14 0V6M5 12v6c0 4 14 4 14 0v-6" /></>
        : <><circle cx="9" cy="8" r="3" /><path d="M3 20v-2a6 4 0 0 1 12 0v2M16 5a3 3 0 1 1 0 6m1 3c3 0 4 2 4 4v2" /></>}
    </svg>
  )
}
