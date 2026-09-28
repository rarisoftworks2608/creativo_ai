import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { fetchPlatformSettings, updatePlatformSettings } from '../api/platformSettings'
import { extractErrorMessage } from '../api/client'

const VARIATION_COUNTS = [1, 2, 3]

export default function AdminSettingsPage() {
  const { isAdmin } = useAuth()

  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!isAdmin) return
    fetchPlatformSettings()
      .then(setSettings)
      .catch((err) => setLoadError(extractErrorMessage(err, 'Could not load settings.')))
      .finally(() => setLoading(false))
  }, [isAdmin])

  if (!isAdmin) return <Navigate to="/companies" replace />

  function updateField(field, value) {
    setSettings((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      const updated = await updatePlatformSettings({
        send_notification_emails: settings.send_notification_emails,
        default_variation_count: Number(settings.default_variation_count),
        max_variation_count: Number(settings.max_variation_count),
        daily_generation_limit_per_company: Number(settings.daily_generation_limit_per_company),
        max_upload_size_mb: Number(settings.max_upload_size_mb),
      })
      setSettings(updated)
      setSaved(true)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save settings.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Admin Settings</h1>
          <p className="page-subtitle">Platform-wide settings that apply to every company.</p>
        </div>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      {loading ? (
        <div className="empty-state">Loading…</div>
      ) : (
        settings && (
          <form onSubmit={handleSubmit}>
            <div className="card">
              <div className="card-header">
                <h2>AI Generation</h2>
              </div>
              <div className="field-row">
                <label className="field">
                  <span>Default variations per request</span>
                  <select
                    value={settings.default_variation_count}
                    onChange={(e) => updateField('default_variation_count', e.target.value)}
                  >
                    {VARIATION_COUNTS.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Max variations an admin can request</span>
                  <select
                    value={settings.max_variation_count}
                    onChange={(e) => updateField('max_variation_count', e.target.value)}
                  >
                    {VARIATION_COUNTS.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="field">
                <span>Daily generation limit per company</span>
                <input
                  type="number"
                  min="0"
                  value={settings.daily_generation_limit_per_company}
                  onChange={(e) => updateField('daily_generation_limit_per_company', e.target.value)}
                />
                <span className="field-hint">Combined creative + video generations a company can start per day. 0 = unlimited.</span>
              </label>
            </div>

            <div className="card">
              <div className="card-header">
                <h2>Notifications</h2>
              </div>
              <label className="field-checkbox">
                <input
                  type="checkbox"
                  checked={settings.send_notification_emails}
                  onChange={(e) => updateField('send_notification_emails', e.target.checked)}
                />
                Send notification emails platform-wide (each user can still opt out individually in their own settings)
              </label>
            </div>

            <div className="card">
              <div className="card-header">
                <h2>Storage</h2>
              </div>
              <label className="field">
                <span>Max brand asset upload size (MB)</span>
                <input
                  type="number"
                  min="1"
                  value={settings.max_upload_size_mb}
                  onChange={(e) => updateField('max_upload_size_mb', e.target.value)}
                />
              </label>
            </div>

            {error && <div className="alert alert-error">{error}</div>}
            {saved && <div className="alert alert-success">Settings saved.</div>}

            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving…' : 'Save settings'}
            </button>
          </form>
        )
      )}

      {settings && (
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-header">
            <h2>Environment (.env-controlled)</h2>
          </div>
          <p className="page-subtitle" style={{ marginBottom: 12 }}>
            These require editing the server's .env file and a restart — not editable here.
          </p>
          <dl className="detail-list">
            <div className="detail-row">
              <dt>AI text provider</dt>
              <dd>{settings.environment.ai_text_provider} — {settings.environment.ai_text_model}</dd>
            </div>
            <div className="detail-row">
              <dt>AI image provider</dt>
              <dd>{settings.environment.ai_image_provider} — {settings.environment.ai_image_model}</dd>
            </div>
            <div className="detail-row">
              <dt>AI video provider</dt>
              <dd>{settings.environment.ai_video_provider} — {settings.environment.ai_video_model}</dd>
            </div>
            <div className="detail-row">
              <dt>Server timezone</dt>
              <dd>{settings.environment.time_zone}</dd>
            </div>
          </dl>
        </div>
      )}
    </div>
  )
}
