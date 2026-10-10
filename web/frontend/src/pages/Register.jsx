import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ShieldCheck, UserPlus, WarningCircle } from '@phosphor-icons/react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { isOperatorEmail, normalizeOperatorEmail } from '../lib/operatorEmail'

export function Register() {
  const { login } = useAuth()
  const navigate = useNavigate()

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
      const data = await api('/auth/register', {
        method: 'POST',
        body: { email: normalizeOperatorEmail(email), password },
      })
      login(data.token, data.email)
      navigate('/console', { replace: true })
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
          <ShieldCheck size={26} color="var(--accent)" />
          <div>
            <h1 className="auth-card__title">Operator registration</h1>
            <p className="auth-card__sub">
              Create an account to run ANPR detection, search vehicles and
              reconstruct trajectories.
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
            <label className="field__label" htmlFor="register-email">
              Operator email
            </label>
            <input
              id="register-email"
              className="input"
              type="email"
              autoComplete="email"
              placeholder="sriram.cop@gmail.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
            <span className="field__hint">
              Registration is restricted to emails containing{' '}
              <span className="mono">.cop@</span> — validated on the server
              as well.
            </span>
          </div>

          <div className="field">
            <label className="field__label" htmlFor="register-password">
              Password
            </label>
            <input
              id="register-password"
              className="input"
              type="password"
              autoComplete="new-password"
              placeholder="Minimum 8 characters"
              minLength={8}
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
            <UserPlus size={15} />
            {busy ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="auth-card__switch">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
