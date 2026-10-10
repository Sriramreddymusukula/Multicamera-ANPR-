import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { LockSimple, SignIn, WarningCircle } from '@phosphor-icons/react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { isOperatorEmail, normalizeOperatorEmail } from '../lib/operatorEmail'

export function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    if (!isOperatorEmail(email)) {
      setError('Use an operator email such as sriram.cop@gmail.com.')
      return
    }
    setBusy(true)
    setError(null)

    try {
      const data = await api('/auth/login', {
        method: 'POST',
        body: { email: normalizeOperatorEmail(email), password },
      })
      login(data.token, data.email)
      navigate(location.state?.from || '/console', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card reveal">
        <div className="auth-card__brand">
          <LockSimple size={26} color="var(--accent)" />
          <div>
            <h1 className="auth-card__title">Operator login</h1>
            <p className="auth-card__sub">
              ANPR detection, vehicle search and tracking require an operator
              account.
            </p>
          </div>
        </div>

        {error && (
          <div className="alert alert--error">
            <WarningCircle size={17} style={{ flex: 'none', marginTop: 1 }} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={submit}>
          <div className="field">
            <label className="field__label" htmlFor="login-email">
              Operator email
            </label>
            <input
              id="login-email"
              className="input"
              type="email"
              autoComplete="email"
              placeholder="sriram.cop@gmail.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
            <span className="field__hint">
              Only <span className="mono">.cop@</span> addresses are accepted.
            </span>
          </div>

          <div className="field">
            <label className="field__label" htmlFor="login-password">
              Password
            </label>
            <input
              id="login-password"
              className="input"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn--primary"
            style={{ width: '100%' }}
            disabled={busy}
          >
            <SignIn size={15} />
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="auth-card__switch">
          New operator? <Link to="/register">Create an account</Link>
        </p>
      </div>
    </div>
  )
}
