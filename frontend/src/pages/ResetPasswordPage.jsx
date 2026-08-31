import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { resetPassword } from '../api/auth'
import { extractErrorMessage } from '../api/client'

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const uid = searchParams.get('uid') || ''
  const token = searchParams.get('token') || ''

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    setSubmitting(true)
    try {
      await resetPassword({ uid, token, newPassword })
      setDone(true)
      setTimeout(() => navigate('/login', { replace: true }), 2000)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not reset your password. The link may have expired.'))
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
          <h1>Reset password</h1>
          <p className="auth-subtitle">Choose a new password for your account.</p>

          {!uid || !token ? (
            <div className="alert alert-error">This reset link is invalid. Request a new one.</div>
          ) : done ? (
            <div className="alert alert-success">Password reset. Redirecting you to sign in…</div>
          ) : (
            <>
              {error && <div className="alert alert-error">{error}</div>}
              <label className="field">
                <span>New password</span>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  autoComplete="new-password"
                  autoFocus
                  required
                />
              </label>
              <label className="field">
                <span>Confirm new password</span>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  autoComplete="new-password"
                  required
                />
              </label>
              <button type="submit" className="btn btn-primary btn-block auth-submit" disabled={submitting}>
                <span>{submitting ? 'Resetting…' : 'Reset password'}</span>
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
