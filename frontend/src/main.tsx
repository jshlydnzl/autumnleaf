import { StrictMode, useEffect, useLayoutEffect, useRef, useState, type MouseEvent } from 'react'
import { createRoot } from 'react-dom/client'
import { ApiError, message, read, write, type Account } from './api'
import { Accounts } from './accounts'
import { AuthScreen } from './auth-screen'
import { Leaf, NavIcon } from './brand'
import { DataExplorer } from './data-explorer'
import { PipelineLab } from './pipeline-lab'
import './index.css'

const nav = [
  ['/', 'Workspace', 'workspace'],
  ['/data', 'Data Explorer', 'data'],
  ['/pipelines', 'Pipeline Lab', 'pipeline'],
  ['/accounts', 'Accounts', 'accounts'],
] as const

function Workspace({ account }: { account: Account }) {
  const [workspace, setWorkspace] = useState<{ name: string, publishedRows: number } | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      read<{ workspace: { name: string } }>('workspaces/' + account.id + '/', controller.signal),
      read<{ total: number }>('warehouse/', controller.signal),
    ])
      .then(([{ workspace }, { total }]) => {
        if (!controller.signal.aborted) setWorkspace({ name: workspace.name, publishedRows: total })
      })
      .catch(err => {
        if (!controller.signal.aborted) setError(message(err))
      })
    return () => controller.abort()
  }, [account.id])

  return (
    <>
      <div className="page-heading">
        <div><p className="eyebrow">Your warehouse</p><h1>Workspace</h1><p className="muted">Explore the data in your personal workspace.</p></div>
      </div>
      {error && <p className="feedback" role="alert">{error}</p>}
      <div className="workspace-grid">
        <section className="panel data-panel" aria-labelledby="datasets">
          <div className="panel-head"><h2 id="datasets">Datasets</h2></div>
          <div className="empty-workspace">
            <NavIcon name="workspace" />
            <p role="status">{workspace ? (workspace.publishedRows ? 'Published sales data available' : 'No published data yet')
              : error ? 'Workspace unavailable' : 'Loading workspace…'}</p>
            {workspace && <a className="button" href={workspace.publishedRows ? '/data' : '/pipelines'}>
              {workspace.publishedRows ? 'Open Data Explorer' : 'Open Pipeline Lab'}
            </a>}
          </div>
        </section>
        <aside className="panel inspector" aria-labelledby="workspace-info">
          <div className="panel-head"><h2 id="workspace-info">Workspace details</h2></div>
          <dl>
            <div><dt>Name</dt><dd>{workspace?.name || '—'}</dd></div>
            <div><dt>Owner</dt><dd>{account.username}</dd></div>
            <div><dt>Visibility</dt><dd>Private</dd></div>
          </dl>
        </aside>
      </div>
    </>
  )
}

function Shell({ account, signOut }: {
  account: Account, signOut: () => Promise<void>,
}) {
  const [requested, setRequested] = useState(() => window.location.pathname)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const routes = nav.filter(([href]) => href !== '/accounts' || account.role === 'admin')
  const path = routes.some(([href]) => href === requested) ? requested : '/'
  const main = useRef<HTMLElement>(null)
  const previousPath = useRef(path)

  useEffect(() => {
    const onBackOrForward = () => setRequested(window.location.pathname)
    window.addEventListener('popstate', onBackOrForward)
    return () => window.removeEventListener('popstate', onBackOrForward)
  }, [])

  useLayoutEffect(() => {
    if (previousPath.current === path) return
    previousPath.current = path
    main.current?.scrollTo(0, 0)
    window.scrollTo(0, 0)
    main.current?.focus({ preventScroll: true })
  }, [path])

  function navigate(event: MouseEvent<HTMLDivElement>) {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
    const link = event.target instanceof Element ? event.target.closest('a[href]') : null
    if (!(link instanceof HTMLAnchorElement) || link.target || link.hasAttribute('download')) return
    const { origin, pathname, search, hash } = new URL(link.href)
    if (origin !== window.location.origin || search || hash || !routes.some(([href]) => href === pathname)) return
    event.preventDefault()
    if (pathname === requested && !window.location.hash && !window.location.search) return
    window.history.pushState(null, '', pathname)
    setRequested(pathname)
  }

  return (
    <div className="app-shell" onClick={navigate}>
      <a className="skip-link button" href="#workspace-content">Skip to content</a>
      <header className="app-header">
        <a className="brand" href="/"><Leaf /> AutumnLeaf</a>
        <div className="session-controls">
          <div className="session-name"><span>{account.username}</span><span className="status capitalize">{account.role}</span></div>
          <button className="button" type="button" disabled={busy} onClick={async () => {
            setError('')
            setBusy(true)
            try { await signOut() } catch (err) { setError(message(err)); setBusy(false) }
          }}>Sign out</button>
        </div>
      </header>
      <nav className="app-nav" aria-label="Workspace navigation">
        <p className="eyebrow">Workspace</p>
        {routes.map(([href, label, icon]) => (
          <a key={href} href={href} aria-current={path === href ? 'page' : undefined}><NavIcon name={icon} /> <span>{label}</span></a>
        ))}
      </nav>
      <main ref={main} id="workspace-content" className="app-main" tabIndex={-1}>
        {error && <p className="feedback" role="alert">{error}</p>}
        {path === '/accounts' ? <Accounts signedIn={account} />
          : path === '/data' ? <DataExplorer />
            : path === '/pipelines' ? <PipelineLab /> : <Workspace account={account} />}
      </main>
    </div>
  )
}

function App() {
  const isSetup = window.location.pathname === '/setup'
  const [account, setAccount] = useState<Account | null>(null)
  const [loading, setLoading] = useState(!isSetup)
  const [error, setError] = useState('')

  useEffect(() => {
    if (isSetup) return
    const controller = new AbortController()
    const expire = () => {
      setAccount(null)
      setError('Your session ended. Sign in to continue.')
    }
    window.addEventListener('autumnleaf:session-expired', expire)
    read<{ account: Account }>('auth/session/', controller.signal)
      .then(result => {
        if (!controller.signal.aborted) setAccount(result.account)
      })
      .catch(err => {
        if (!controller.signal.aborted && !(err instanceof ApiError && err.status === 401)) setError(message(err))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => {
      controller.abort()
      window.removeEventListener('autumnleaf:session-expired', expire)
    }
  }, [isSetup])

  if (loading) return <main className="center-state" role="status">Opening AutumnLeaf…</main>
  if (!account || isSetup) return (
    <>
      {error && <p className="session-error feedback" role="alert">{error}</p>}
      <AuthScreen isSetup={isSetup} onSignIn={next => {
        setError('')
        if (window.location.pathname === '/accounts' && next.role !== 'admin') window.history.replaceState(null, '', '/')
        setAccount(next)
      }} />
    </>
  )
  return (
    <Shell account={account} signOut={async () => {
      await write('auth/logout/', 'POST')
      window.history.replaceState(null, '', '/')
      setAccount(null)
    }} />
  )
}

const root = document.getElementById('root')
if (!root) throw new Error('Missing application root')
createRoot(root).render(<StrictMode><App /></StrictMode>)
