import { useEffect, useState } from 'react'
import { fetchLoginHistory, updateProfile } from '../api/auth'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import ChangePasswordModal from '../components/ChangePasswordModal'

const EMPTY_FORM = {
  first_name: '', last_name: '', phone_number: '', email_notifications_enabled: true, whatsapp_notifications_enabled: false,
}

export default function SettingsPage() {
  const { user, setUser } = useAuth()

  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  const [showChangePassword, setShowChangePassword] = useState(false)
  const [loginHistory, setLoginHistory] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(true)

  useEffect(() => {
    if (!user) return
    setForm({
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      phone_number: user.phone_number || '',
      email_notifications_enabled: user.email_notifications_enabled ?? true,
      whatsapp_notifications_enabled: user.whatsapp_notifications_enabled ?? false,
    })
  }, [user])

  useEffect(() => {
    fetchLoginHistory()
      .then((data) => setLoginHistory(data.results))
      .catch(() => {})
      .finally(() => setLoadingHistory(false))
  }, [])

  function updateField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      const updated = await updateProfile({ ...form })
      setUser(updated)
      setSaved(true)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save your settings.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>My Account</h1>
          <p className="page-subtitle">Manage your profile, security, and notification preferences.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="card">
          <div className="card-header">
            <h2>Profile</h2>
          </div>

          {error && <div className="alert alert-error">{error}</div>}
          {saved && <div className="alert alert-success">Your changes have been saved.</div>}

          <div className="field-row">
            <label className="field">
              <span>First name</span>
              <input value={form.first_name} onChange={(e) => updateField('first_name', e.target.value)} />
            </label>
            <label className="field">
              <span>Last name</span>
              <input value={form.last_name} onChange={(e) => updateField('last_name', e.target.value)} />
            </label>
          </div>

          <label className="field">
            <span>Email</span>
            <input value={user?.email || ''} disabled />
          </label>

          <label className="field">
            <span>Phone number (with country code)</span>
            <input value={form.phone_number} inputMode="tel" placeholder="+91 98765 43210" onChange={(e) => updateField('phone_number', e.target.value)} />
          </label>
        </div>

        <div className="card">
          <div className="card-header">
            <h2>Notifications</h2>
          </div>
          <label className="field-checkbox">
            <input
              type="checkbox"
              checked={form.email_notifications_enabled}
              onChange={(e) => updateField('email_notifications_enabled', e.target.checked)}
            />
            Email me when there's new activity on my account
          </label>
          <label className="field-checkbox">
            <input
              type="checkbox"
              checked={form.whatsapp_notifications_enabled}
              onChange={(e) => updateField('whatsapp_notifications_enabled', e.target.checked)}
            />
            Send me WhatsApp updates (approval requests, reminders, published posts, monthly reports) on my phone number
          </label>
          {form.whatsapp_notifications_enabled && !form.phone_number && (
            <p className="field-hint">Add your phone number above (with country code, e.g. +91…) to receive WhatsApp updates.</p>
          )}
        </div>

        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? 'Saving…' : 'Save changes'}
        </button>
      </form>

      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-header">
          <h2>Security</h2>
          <button type="button" className="btn btn-ghost" onClick={() => setShowChangePassword(true)}>
            Change password
          </button>
        </div>
        <p className="page-subtitle" style={{ marginBottom: 12 }}>
          Recent login activity
        </p>
        {loadingHistory ? (
          <p className="muted">Loading…</p>
        ) : loginHistory.length === 0 ? (
          <p className="muted">No login history yet.</p>
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Status</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {loginHistory.slice(0, 10).map((entry) => (
                  <tr key={entry.id}>
                    <td>{new Date(entry.created_at).toLocaleString()}</td>
                    <td>
                      <span className={`badge badge-${entry.was_successful ? 'active' : 'inactive'}`}>
                        {entry.was_successful ? 'Success' : 'Failed'}
                      </span>
                    </td>
                    <td>{entry.ip_address || <span className="muted">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showChangePassword && <ChangePasswordModal onClose={() => setShowChangePassword(false)} />}
    </div>
  )
}
