import { useState, type FormEvent } from 'react'
import { Leaf } from './brand'
import { message, write, type Account } from './api'

export function AuthScreen({ isSetup, onSignIn }: { isSetup: boolean, onSignIn: (account: Account) => void }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [complete, setComplete] = useState(false)
  const hasLink = Boolean(window.location.hash.slice(1))

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const password = String(form.get('password'))
    setError('')
    if (isSetup && password !== form.get('confirm')) {
      setError('Passwords do not match.')
      return
    }
    setBusy(true)
    try {
      if (isSetup) {
        await write('auth/setup/', 'POST', { token: window.location.hash.slice(1), password })
        window.history.replaceState(null, '', '/setup')
        setComplete(true)
      } else {
        const { account } = await write<{ account: Account }>('auth/login/', 'POST', {
          username: form.get('username'), password,
        })
        onSignIn(account)
      }
    } catch (err) {
      setError(message(err))
    } finally {
      setBusy(false)
    }
  }

  const title = complete ? 'Password saved' : isSetup ? 'Set your password' : 'Sign in'
  return (
    <main className="auth-layout">
      <aside className="auth-cover" aria-hidden="true">
        <div className="brand"><Leaf /> AutumnLeaf</div>
        <Leaf className="cover-leaf" />
        <div className="cover-copy">
          <span className="eyebrow">Personal warehouse</span>
          <p>A quiet place<br />to work with data.</p>
        </div>
      </aside>
      <section className="auth-content" aria-labelledby="auth-title">
        <div className="auth-card">
          <div className="brand auth-brand"><Leaf /> AutumnLeaf</div>
          <p className="eyebrow">{isSetup ? 'Account access' : 'Private workspace'}</p>
          <h1 id="auth-title">{title}</h1>
          <p className="muted">{complete ? 'You can now sign in with your new password.'
            : isSetup ? 'Choose a password with at least 12 characters.'
              : 'Enter your AutumnLeaf username and password.'}</p>
          {complete ? <a className="button primary" href="/">Go to sign-in</a>
            : isSetup && !hasLink ? <p className="feedback" role="alert">This setup link is incomplete. Ask an Admin for a new one.</p>
              : (
                <form className="auth-form" onSubmit={submit}>
                  {!isSetup && <label>Username<input name="username" autoComplete="username" required maxLength={32} /></label>}
                  <label>Password<input name="password" type="password" autoComplete={isSetup ? 'new-password' : 'current-password'} required minLength={isSetup ? 12 : undefined} maxLength={128} /></label>
                  {isSetup && <label>Confirm password<input name="confirm" type="password" autoComplete="new-password" required minLength={12} maxLength={128} /></label>}
                  {error && <p className="feedback" role="alert">{error}</p>}
                  <button className="button primary" disabled={busy}>{busy ? 'Working…' : isSetup ? 'Save password' : 'Sign in'}</button>
                </form>
              )}
          {!isSetup && <p className="auth-note">Access is by invitation. Contact your Admin if you need an account.</p>}
        </div>
      </section>
    </main>
  )
}
