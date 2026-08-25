import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { extractErrorMessage } from '../api/client'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const loggedInUser = await login(email, password)
      const homePath = loggedInUser.role === 'admin' ? '/companies' : '/client'
      navigate(location.state?.from || homePath, { replace: true })
    } catch (err) {
      setError(extractErrorMessage(err, 'Invalid email or password.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-bg" aria-hidden="true">
        <span className="auth-blob auth-blob-1" />
        <span className="auth-blob auth-blob-2" />
        <span className="auth-blob auth-blob-3" />
        <span className="auth-grid" />
      </div>

      <div className="auth-panel">
        <div className="auth-showcase" aria-hidden="true">
          <div className="auth-showcase-badge">
            <span className="brand-mark brand-mark-glow">AI</span>
            <span>Marketing OS</span>
          </div>
          <h2 className="auth-showcase-title">
            Run every client's marketing
            <br />
            from one command center.
          </h2>
          <p className="auth-showcase-copy">
            Content calendars, AI-generated creatives, and video — planned, approved, and shipped in one place.
          </p>
          <ul className="auth-showcase-stats">
            <li>
              <strong>AI</strong>
              <span>Strategy &amp; creative generation</span>
            </li>
            <li>
              <strong>1</strong>
              <span>Dashboard for every company you run</span>
            </li>
            <li>
              <strong>0</strong>
              <span>Spreadsheets left behind</span>
            </li>
          </ul>
        </div>

        <form className="auth-card" onSubmit={handleSubmit}>
          <div className="auth-brand">
            <span className="brand-mark">AI</span>
            <span>Marketing OS</span>
          </div>
          <h1>Welcome back</h1>
          <p className="auth-subtitle">Sign in to manage your companies and campaigns.</p>

          {error && <div className="alert alert-error">{error}</div>}

          <label className="field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </label>

          <label className="field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </label>

          <button type="submit" className="btn btn-primary btn-block auth-submit" disabled={submitting}>
            <span>{submitting ? 'Signing in…' : 'Sign in'}</span>
          </button>
        </form>
      </div>
    </div>
  )
}
