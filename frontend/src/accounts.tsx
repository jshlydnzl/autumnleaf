import { Fragment, useEffect, useState, type FormEvent } from 'react'
import { message, read, write, type Account } from './api'

type AccountChange = { account: Account, token?: string }

export function Accounts({ signedIn }: { signedIn: Account }) {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [invite, setInvite] = useState('')
  const [copied, setCopied] = useState(false)
  const [managedId, setManagedId] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    read<{ accounts: Account[] }>('accounts/', controller.signal)
      .then(result => {
        if (!controller.signal.aborted) setAccounts(result.accounts)
      })
      .catch(err => {
        if (!controller.signal.aborted) setError(message(err))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [])

  async function change(path: string, method: 'POST' | 'PATCH', data: object) {
    setBusy(true)
    setError('')
    setCopied(false)
    setInvite('')
    try {
      const result = await write<AccountChange>(path, method, data)
      setAccounts(current => [...current.filter(row => row.id !== result.account.id), result.account]
        .sort((a, b) => a.username.localeCompare(b.username)))
      if (result.token) setInvite(window.location.origin + '/setup#' + result.token)
      if (method === 'POST') setShowForm(false)
      setManagedId('')
    } catch (err) {
      setError(message(err))
    } finally {
      setBusy(false)
    }
  }

  function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    void change('accounts/', 'POST', { username: form.get('username'), role: form.get('role') })
  }

  return (
    <>
      <div className="page-heading">
        <div><p className="eyebrow">Workspace access</p><h1>Accounts</h1><p className="muted">Invite people and manage their access to AutumnLeaf.</p></div>
        <button className="button primary" type="button" aria-expanded={showForm} onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : 'Create account'}
        </button>
      </div>
      {error && <p className="feedback" role="alert">{error}</p>}
      {showForm && (
        <form className="panel inline-form" onSubmit={create} aria-label="New account">
          <label>Username<input name="username" autoComplete="off" required minLength={3} maxLength={32} /></label>
          <label>Role<select name="role"><option value="member">Member</option><option value="admin">Admin</option></select></label>
          <button className="button primary" disabled={busy}>{busy ? 'Creating…' : 'Create setup link'}</button>
        </form>
      )}
      {invite && (
        <section className="panel setup-link" aria-label="Setup link">
          <h2>Setup link ready</h2>
          <p className="muted">Share it privately. It expires after 24 hours and works once.</p>
          <div className="link-row">
            <input aria-label="Setup link" readOnly value={invite} onFocus={event => event.target.select()} />
            <button className="button" type="button" onClick={async () => {
              try {
                await navigator.clipboard.writeText(invite)
                setCopied(true)
              } catch {
                setError('Clipboard unavailable. Select the link and copy it manually.')
              }
            }}>{copied ? 'Copied' : 'Copy link'}</button>
            <button className="button" type="button" onClick={() => setInvite('')}>Hide</button>
          </div>
        </section>
      )}
      <section className="panel account-panel" aria-label="Account list">
        <div className="panel-head"><h2>People</h2><span className="muted">{loading ? 'Loading…' : accounts.length + (accounts.length === 1 ? ' account' : ' accounts')}</span></div>
        {!loading && accounts.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead><tr><th scope="col">Username</th><th scope="col">Role</th><th scope="col">Status</th><th scope="col">Actions</th></tr></thead>
              <tbody>
                {accounts.map(account => {
                  const isSelf = account.id === signedIn.id
                  const path = 'accounts/' + account.id + '/'
                  return (
                    <Fragment key={account.id}>
                      <tr>
                        <th scope="row">{account.username}{isSelf && <span className="muted"> · You</span>}</th>
                        <td className="capitalize">{account.role}</td>
                        <td><span className={'status ' + account.status}>{account.status}</span></td>
                        <td>
                          {!isSelf && <button type="button" className="button" aria-expanded={managedId === account.id} aria-label={'Manage ' + account.username}
                            onClick={() => setManagedId(managedId === account.id ? '' : account.id)}>Manage</button>}
                        </td>
                      </tr>
                      {!isSelf && managedId === account.id && (
                        <tr>
                          <td colSpan={4}>
                            <div className="account-actions" role="group" aria-label={'Actions for ' + account.username}>
                              {account.status !== 'disabled' && <button type="button" className="button" disabled={busy}
                                onClick={() => void change(path, 'PATCH', { action: 'issue_link' })}>Issue new link</button>}
                              <button type="button" className="button" disabled={busy}
                                onClick={() => void change(path, 'PATCH', { action: 'set_role', role: account.role === 'admin' ? 'member' : 'admin' })}>
                                Make {account.role === 'admin' ? 'Member' : 'Admin'}
                              </button>
                              <button type="button" className="button" disabled={busy}
                                onClick={() => void change(path, 'PATCH', { action: account.status === 'disabled' ? 'reactivate' : 'disable' })}>
                                {account.status === 'disabled' ? 'Reactivate account' : 'Disable account'}
                              </button>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        {!loading && !error && accounts.length === 0 && <p className="muted panel-head">No accounts found.</p>}
      </section>
    </>
  )
}
