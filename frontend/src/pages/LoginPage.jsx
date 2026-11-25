import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { extractErrorMessage } from '../api/client'
import AuthLayout from '../components/AuthLayout'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [phase, setPhase] = useState('idle') // idle | loading | done
  const [welcomeName, setWelcomeName] = useState('')
  const timer = useRef(null)

  useEffect(() => () => clearTimeout(timer.current), [])

  async function handleSubmit(event) {
    event.preventDefault()
    if (phase !== 'idle') return
    setError('')
    setPhase('loading')
    try {
      const loggedInUser = await login(email, password)
      const homePath = loggedInUser.role === 'admin' ? '/dashboard' : '/client'
      setWelcomeName((loggedInUser.full_name || '').trim().split(/\s+/)[0] || '')
      setPhase('done')
      // A short beat so the confirmation tick is seen before the app opens.
      timer.current = setTimeout(() => navigate(location.state?.from || homePath, { replace: true }), 450)
    } catch (err) {
      setError(extractErrorMessage(err, 'Invalid email or password.'))
      setPhase('idle')
    }
  }

  return (
    <AuthLayout>
      <form className="signin-form" onSubmit={handleSubmit}>
        <div className="signin-heading signin-rise" style={{ animationDelay: '0.08s' }}>
          <h1>Welcome back</h1>
          <p>Sign in to plan, create and publish for every brand you manage.</p>
        </div>

        {error && (
          <div className="signin-error" role="alert">
            {error}
          </div>
        )}

        <label className="signin-field signin-rise" style={{ animationDelay: '0.16s' }}>
          <span className="signin-label">Work email</span>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            placeholder="you@company.com"
            required
          />
        </label>

        <label className="signin-field signin-rise" style={{ animationDelay: '0.24s' }}>
          <span className="signin-label signin-label-row">
            Password
            <Link to="/forgot-password">Forgot password?</Link>
          </span>
          <span className="signin-input-wrap">
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              placeholder="Your password"
              required
            />
            <button
              type="button"
              className="signin-eye"
              onClick={() => setShowPassword((prev) => !prev)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              aria-pressed={showPassword}
            >
              {showPassword ? (
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M3 3l18 18M10.6 5.1A10.6 10.6 0 0 1 12 5c6.5 0 10 7 10 7a17.4 17.4 0 0 1-3.2 4.2M6.6 6.6C3.9 8.3 2 12 2 12s3.5 7 10 7a9.7 9.7 0 0 0 5.4-1.6M9.9 9.9a3 3 0 0 0 4.2 4.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" stroke="currentColor" strokeWidth="1.8" />
                  <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
                </svg>
              )}
            </button>
          </span>
        </label>

        <button
          type="submit"
          className={`signin-submit signin-rise ${phase === 'done' ? 'is-done' : ''}`}
          style={{ animationDelay: '0.32s' }}
          disabled={phase !== 'idle'}
          aria-live="polite"
        >
          {phase === 'idle' && (
            <>
              Sign in
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
              </svg>
            </>
          )}
          {phase === 'loading' && (
            <>
              <span className="signin-spinner" aria-hidden="true" />
              Signing in…
            </>
          )}
          {phase === 'done' && (
            <>
              <svg className="signin-tick" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M5 12.5l4.5 4.5L19 7.5" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {welcomeName ? `Welcome, ${welcomeName}` : 'Welcome back'}
            </>
          )}
        </button>

        <p className="signin-note signin-rise" style={{ animationDelay: '0.4s' }}>
          Clients get access through an invite from their agency.
        </p>
      </form>
    </AuthLayout>
  )
}
