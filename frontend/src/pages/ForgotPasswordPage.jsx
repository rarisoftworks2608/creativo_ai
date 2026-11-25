import { useState } from 'react'
import { Link } from 'react-router-dom'
import { requestPasswordReset } from '../api/auth'
import { extractErrorMessage } from '../api/client'
import AuthLayout from '../components/AuthLayout'

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
    <AuthLayout>
      <form className="signin-form" onSubmit={handleSubmit}>
        <div className="signin-heading signin-rise">
          <h1>Forgot password</h1>
          <p>Enter your account email and we'll send you a reset link.</p>
        </div>

          {error && <div className="signin-error" role="alert">{error}</div>}

          {sent ? (
            <div className="signin-success" role="status">
              If an account exists for that email, a reset link has been sent. Check your inbox.
            </div>
          ) : (
            <>
              <label className="signin-field">
                <span className="signin-label">Email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  autoFocus
                  required
                />
              </label>
              <button type="submit" className="signin-submit" disabled={submitting}>
                {submitting ? 'Sending…' : 'Send reset link'}
              </button>
            </>
          )}

        <p className="signin-note">
          <Link to="/login">← Back to sign in</Link>
        </p>
      </form>
    </AuthLayout>
  )
}
