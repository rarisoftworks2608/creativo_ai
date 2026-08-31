import { useState } from 'react'
import { changePassword } from '../api/auth'
import { extractErrorMessage } from '../api/client'
import Modal from './Modal'

export default function ChangePasswordModal({ onClose }) {
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.')
      return
    }
    setSubmitting(true)
    try {
      await changePassword({ oldPassword, newPassword })
      setDone(true)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not change your password.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal title="Change password" onClose={onClose}>
      {done ? (
        <>
          <div className="alert alert-success">Your password has been changed.</div>
          <div className="modal-actions">
            <button type="button" className="btn btn-primary" onClick={onClose}>
              Done
            </button>
          </div>
        </>
      ) : (
        <form onSubmit={handleSubmit}>
          {error && <div className="alert alert-error">{error}</div>}
          <label className="field">
            <span>Current password</span>
            <input
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              autoComplete="current-password"
              autoFocus
              required
            />
          </label>
          <label className="field">
            <span>New password</span>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </label>
          <label className="field">
            <span>Confirm new password</span>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </label>
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Saving…' : 'Change password'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  )
}
