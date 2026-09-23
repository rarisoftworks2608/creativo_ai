import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
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
      const homePath = loggedInUser.role === 'admin' ? '/dashboard' : '/client'
      navigate(location.state?.from || homePath, { replace: true })
    } catch (err) {
      setError(extractErrorMessage(err, 'Invalid email or password.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-panel auth-panel-single">
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

          <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>

          <p className="auth-footer-link">
            <Link to="/forgot-password">Forgot password?</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
