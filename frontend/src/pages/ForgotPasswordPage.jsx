import { useState } from 'react'
import { Link } from 'react-router-dom'
import { requestPasswordReset } from '../api/auth'
import { extractErrorMessage } from '../api/client'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await requestPasswordReset(email)
      setSent(true)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not send the reset email.'))
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

      <div className="auth-panel auth-panel-single">
        <form className="auth-card" onSubmit={handleSubmit}>
          <div className="auth-brand">
            <span className="brand-mark">AI</span>
            <span>Marketing OS</span>
          </div>
          <h1>Forgot password</h1>
          <p className="auth-subtitle">Enter your account email and we'll send you a reset link.</p>

          {error && <div className="alert alert-error">{error}</div>}

          {sent ? (
            <div className="alert alert-success">
              If an account exists for that email, a reset link has been sent. Check your inbox.
            </div>
          ) : (
            <>
              <label className="field">
                <span>Email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  autoFocus
                  required
                />
              </label>
              <button type="submit" className="btn btn-primary btn-block auth-submit" disabled={submitting}>
                <span>{submitting ? 'Sending…' : 'Send reset link'}</span>
              </button>
            </>
          )}

          <p className="auth-footer-link">
            <Link to="/login">← Back to sign in</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
