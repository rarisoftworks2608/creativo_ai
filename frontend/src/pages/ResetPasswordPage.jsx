import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { resetPassword } from '../api/auth'
import { extractErrorMessage } from '../api/client'
import AuthLayout from '../components/AuthLayout'

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
    <AuthLayout>
      <form className="signin-form" onSubmit={handleSubmit}>
        <div className="signin-heading signin-rise">
          <h1>Reset password</h1>
          <p>Choose a new password for your account.</p>
        </div>

          {!uid || !token ? (
            <div className="signin-error" role="alert">This reset link is invalid. Request a new one.</div>
          ) : done ? (
            <div className="signin-success" role="status">Password reset. Redirecting you to sign in…</div>
          ) : (
            <>
              {error && <div className="signin-error" role="alert">{error}</div>}
              <label className="signin-field">
                <span className="signin-label">New password</span>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  autoComplete="new-password"
                  autoFocus
                  required
                />
              </label>
              <label className="signin-field">
                <span className="signin-label">Confirm new password</span>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  autoComplete="new-password"
                  required
                />
              </label>
              <button type="submit" className="signin-submit" disabled={submitting}>
                {submitting ? 'Resetting…' : 'Reset password'}
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
