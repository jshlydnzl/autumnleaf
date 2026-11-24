import { StrictMode, useEffect, useState, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { ApiError, message, read, write, type Account } from './api'
import { Accounts } from './accounts'
import { AuthScreen } from './auth-screen'
import { Leaf, NavIcon } from './brand'
import './index.css'

function Workspace({ account }: { account: Account }) {
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    read<{ workspace: { name: string } }>('workspaces/' + account.id + '/', controller.signal)
      .then(({ workspace }) => {
        if (!controller.signal.aborted) setName(workspace.name)
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
            <p role="status">{name ? 'No datasets yet' : error ? 'Workspace unavailable' : 'Loading workspace…'}</p>
          </div>
        </section>
        <aside className="panel inspector" aria-labelledby="workspace-info">
          <div className="panel-head"><h2 id="workspace-info">Workspace details</h2></div>
          <dl>
            <div><dt>Name</dt><dd>{name || '—'}</dd></div>
            <div><dt>Owner</dt><dd>{account.username}</dd></div>
            <div><dt>Visibility</dt><dd>Private</dd></div>
          </dl>
        </aside>
      </div>
    </>
  )
}

function Shell({ account, isAccounts, signOut, children }: {
  account: Account, isAccounts: boolean, signOut: () => Promise<void>, children: ReactNode,
}) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  return (
    <div className="app-shell">
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
        <a href="/" aria-current={!isAccounts ? 'page' : undefined}><NavIcon name="workspace" /> <span>Workspace</span></a>
        {account.role === 'admin' && <a href="/accounts" aria-current={isAccounts ? 'page' : undefined}><NavIcon name="accounts" /> <span>Accounts</span></a>}
      </nav>
      <main id="workspace-content" className="app-main" tabIndex={-1}>
        {error && <p className="feedback" role="alert">{error}</p>}
        {children}
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
        if (window.location.pathname !== '/' && next.role !== 'admin') window.history.replaceState(null, '', '/')
        setAccount(next)
      }} />
    </>
  )
  const isAccounts = window.location.pathname === '/accounts' && account.role === 'admin'
  return (
    <Shell account={account} isAccounts={isAccounts} signOut={async () => {
      await write('auth/logout/', 'POST')
      window.history.replaceState(null, '', '/')
      setAccount(null)
    }}>
      {isAccounts ? <Accounts signedIn={account} /> : <Workspace account={account} />}
    </Shell>
  )
}

const root = document.getElementById('root')
if (!root) throw new Error('Missing application root')
createRoot(root).render(<StrictMode><App /></StrictMode>)
