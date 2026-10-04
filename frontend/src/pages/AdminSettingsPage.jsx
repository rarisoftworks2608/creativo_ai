import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { fetchPlatformSettings, updatePlatformSettings } from '../api/platformSettings'
import { extractErrorMessage } from '../api/client'

const VARIATION_COUNTS = [1, 2, 3]
const LANGUAGES = [
  ['en', 'English'], ['hi', 'Hindi'], ['mr', 'Marathi'], ['gu', 'Gujarati'], ['ta', 'Tamil'], ['te', 'Telugu'],
  ['kn', 'Kannada'], ['bn', 'Bengali'], ['ml', 'Malayalam'], ['es', 'Spanish'], ['fr', 'French'], ['de', 'German'], ['ar', 'Arabic'],
]
const TIMEZONES = ['Asia/Kolkata', 'Asia/Dubai', 'Asia/Singapore', 'Europe/London', 'Europe/Berlin', 'America/New_York', 'America/Los_Angeles', 'UTC']
const EDITABLE = [
  'send_notification_emails', 'default_variation_count', 'max_variation_count', 'daily_generation_limit_per_company', 'max_upload_size_mb',
  'ai_text_provider', 'ai_text_model', 'ai_image_provider', 'ai_image_model', 'ai_video_provider', 'ai_video_model',
  'default_timezone', 'content_language', 'publishing_enabled', 'auto_schedule_on_approval', 'default_publish_time',
  'publish_max_attempts', 'approval_reminder_hours', 'analytics_sync_enabled', 'analytics_sync_interval_hours',
  'monthly_reports_enabled', 'report_day_of_month', 'email_reports_to_clients', 'whatsapp_reports_to_clients',
  'enforce_subscription_limits', 'subscription_expiry_reminder_days',
]
const NUMERIC = new Set([
  'default_variation_count', 'max_variation_count', 'daily_generation_limit_per_company', 'max_upload_size_mb', 'publish_max_attempts',
  'approval_reminder_hours', 'analytics_sync_interval_hours', 'report_day_of_month', 'subscription_expiry_reminder_days',
])

function Toggle({ checked, onChange, label, hint }) {
  return (
    <label className="setting-toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>
        <strong>{label}</strong>
        {hint && <span className="field-hint-inline">{hint}</span>}
      </span>
    </label>
  )
}

function ProviderField({ kind, label, settings, update }) {
  const env = settings.environment
  const options = env.provider_options[kind] || []
  const effective = env[`ai_${kind}_provider`]
  const credentials = env.credentials[kind] || {}
  return (
    <div className="provider-field">
      <div className="field-row">
        <label className="field">
          <span>{label} provider</span>
          <select value={settings[`ai_${kind}_provider`]} onChange={(e) => update(`ai_${kind}_provider`, e.target.value)}>
            <option value="">Use .env ({env.env_defaults[`ai_${kind}_provider`]})</option>
            {options.map((provider) => (
              <option key={provider} value={provider}>
                {provider} {credentials[provider]?.configured ? '✓' : '(no key)'}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{label} model</span>
          <input
            value={settings[`ai_${kind}_model`]}
            placeholder={env.default_models[`${kind}:${settings[`ai_${kind}_provider`] || effective}`] || env.env_defaults[`ai_${kind}_model`]}
            onChange={(e) => update(`ai_${kind}_model`, e.target.value)}
          />
        </label>
      </div>
      <p className="field-hint-inline">
        In use now: <strong>{effective}</strong> · {env[`ai_${kind}_model`]}
        {credentials[effective] && !credentials[effective].configured && (
          <span className="usage-danger"> - {credentials[effective].env_vars.join(' + ')} not set in .env</span>
        )}
      </p>
    </div>
  )
}

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

  function update(field, value) {
    setSettings((prev) => ({ ...prev, [field]: value }))
    setSaved(false)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      const payload = {}
      EDITABLE.forEach((field) => {
        payload[field] = NUMERIC.has(field) ? Number(settings[field]) : settings[field]
      })
      const updated = await updatePlatformSettings(payload)
      setSettings(updated)
      setSaved(true)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save settings.'))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="page-loading">Loading…</div>
  if (!settings) return <div className="alert alert-error">{loadError}</div>
  const env = settings.environment

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Admin settings</h1>
          <p className="page-subtitle">Platform-wide settings for every company. API keys stay in the server&apos;s .env file.</p>
        </div>
        <Link to="/system-health" className="btn btn-ghost">
          System health
        </Link>
      </div>

      <form onSubmit={handleSubmit} className="settings-form">
        <div className="settings-grid">
          <section className="card">
            <div className="card-header">
              <h2>AI providers & models</h2>
            </div>
            <p className="page-subtitle settings-intro">
              Switch providers without a deploy - e.g. from Cloudflare to OpenAI once <code>OPENAI_API_KEY</code> is in .env.
            </p>
            <ProviderField kind="text" label="Text" settings={settings} update={update} />
            <ProviderField kind="image" label="Image" settings={settings} update={update} />
            <ProviderField kind="video" label="Video motion" settings={settings} update={update} />
          </section>

          <section className="card">
            <div className="card-header">
              <h2>AI generation</h2>
            </div>
            <div className="field-row">
              <label className="field">
                <span>Default variations</span>
                <select value={settings.default_variation_count} onChange={(e) => update('default_variation_count', e.target.value)}>
                  {VARIATION_COUNTS.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Max variations</span>
                <select value={settings.max_variation_count} onChange={(e) => update('max_variation_count', e.target.value)}>
                  {VARIATION_COUNTS.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="field">
              <span>Daily generation limit per company (0 = unlimited)</span>
              <input type="number" min="0" value={settings.daily_generation_limit_per_company} onChange={(e) => update('daily_generation_limit_per_company', e.target.value)} />
            </label>
            <label className="field">
              <span>Content language</span>
              <select value={settings.content_language} onChange={(e) => update('content_language', e.target.value)}>
                {LANGUAGES.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <span className="field-hint-inline">Captions, video scripts and voice-overs are written in this language.</span>
            </label>
          </section>

          <section className="card">
            <div className="card-header">
              <h2>Publishing</h2>
            </div>
            <Toggle checked={settings.publishing_enabled} onChange={(v) => update('publishing_enabled', v)} label="Publishing enabled" hint="Kill switch - when off, scheduled posts wait." />
            <Toggle
              checked={settings.auto_schedule_on_approval}
              onChange={(v) => update('auto_schedule_on_approval', v)}
              label="Auto-schedule on approval"
              hint="Approved content is scheduled to every connected account for its platforms at the planned date/time."
            />
            <div className="field-row">
              <label className="field">
                <span>Default publish time</span>
                <input type="time" value={(settings.default_publish_time || '10:00').slice(0, 5)} onChange={(e) => update('default_publish_time', e.target.value)} />
              </label>
              <label className="field">
                <span>Publish attempts before failing</span>
                <input type="number" min="1" max="10" value={settings.publish_max_attempts} onChange={(e) => update('publish_max_attempts', e.target.value)} />
              </label>
            </div>
            <label className="field">
              <span>Timezone for calendar dates</span>
              <input list="timezones" value={settings.default_timezone} placeholder={env.time_zone} onChange={(e) => update('default_timezone', e.target.value)} />
              <datalist id="timezones">
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz} />
                ))}
              </datalist>
              <span className="field-hint-inline">In use: {env.effective_timezone}</span>
            </label>
          </section>

          <section className="card">
            <div className="card-header">
              <h2>Approvals & notifications</h2>
            </div>
            <label className="field">
              <span>Remind clients after (hours, 0 = off)</span>
              <input type="number" min="0" value={settings.approval_reminder_hours} onChange={(e) => update('approval_reminder_hours', e.target.value)} />
            </label>
            <Toggle
              checked={settings.send_notification_emails}
              onChange={(v) => update('send_notification_emails', v)}
              label="Send notification emails"
              hint="Users can still opt out in their own settings."
            />
            <label className="field">
              <span>Max brand asset upload (MB)</span>
              <input type="number" min="1" value={settings.max_upload_size_mb} onChange={(e) => update('max_upload_size_mb', e.target.value)} />
            </label>
          </section>

          <section className="card">
            <div className="card-header">
              <h2>Analytics & reports</h2>
            </div>
            <Toggle checked={settings.analytics_sync_enabled} onChange={(v) => update('analytics_sync_enabled', v)} label="Sync analytics automatically" />
            <label className="field">
              <span>Sync every (hours)</span>
              <input type="number" min="1" max="48" value={settings.analytics_sync_interval_hours} onChange={(e) => update('analytics_sync_interval_hours', e.target.value)} />
            </label>
            <Toggle checked={settings.monthly_reports_enabled} onChange={(v) => update('monthly_reports_enabled', v)} label="Generate monthly reports" />
            <label className="field">
              <span>Generate on day of month (1-28)</span>
              <input type="number" min="1" max="28" value={settings.report_day_of_month} onChange={(e) => update('report_day_of_month', e.target.value)} />
            </label>
            <Toggle checked={settings.email_reports_to_clients} onChange={(v) => update('email_reports_to_clients', v)} label="Email monthly reports to clients" />
            <Toggle checked={settings.whatsapp_reports_to_clients} onChange={(v) => update('whatsapp_reports_to_clients', v)} label="Send monthly reports on WhatsApp" />
          </section>

          <section className="card">
            <div className="card-header">
              <h2>Subscriptions</h2>
            </div>
            <Toggle
              checked={settings.enforce_subscription_limits}
              onChange={(v) => update('enforce_subscription_limits', v)}
              label="Enforce plan limits"
              hint="Off: usage is tracked but never blocks work. On: generation/publishing stop at the plan limit."
            />
            <label className="field">
              <span>Expiry reminder (days before)</span>
              <input type="number" min="0" max="90" value={settings.subscription_expiry_reminder_days} onChange={(e) => update('subscription_expiry_reminder_days', e.target.value)} />
            </label>
          </section>
        </div>

        {error && <div className="alert alert-error">{error}</div>}
        {saved && <div className="alert alert-success">Settings saved.</div>}
        <div className="form-footer form-footer-sticky">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving…' : 'Save settings'}
          </button>
        </div>
      </form>

      <section className="card">
        <div className="card-header">
          <h2>Integrations (.env)</h2>
        </div>
        <dl className="detail-list">
          <div className="detail-row">
            <dt>Meta (Facebook / Instagram)</dt>
            <dd>
              {env.social_oauth.meta.configured ? '✓ OAuth configured' : '✗ set META_APP_ID + META_APP_SECRET'} · redirect URI{' '}
              <code>{env.social_oauth.meta.redirect_uri}</code>
            </dd>
          </div>
          <div className="detail-row">
            <dt>LinkedIn</dt>
            <dd>
              {env.social_oauth.linkedin.configured ? '✓ OAuth configured' : '✗ set LINKEDIN_CLIENT_ID + LINKEDIN_CLIENT_SECRET'} · redirect URI{' '}
              <code>{env.social_oauth.linkedin.redirect_uri}</code>
            </dd>
          </div>
          <div className="detail-row">
            <dt>WhatsApp</dt>
            <dd>
              {env.whatsapp.provider === 'console' ? 'Test mode (console)' : env.whatsapp.configured ? '✓ Cloud API configured' : '✗ incomplete'}
            </dd>
          </div>
          <div className="detail-row">
            <dt>Media storage</dt>
            <dd>
              {env.storage_backend === 's3' ? 'S3 / R2' : 'Local disk'} · public media URL{' '}
              <code>{env.public_media_base_url || `${env.backend_public_url}/media/`}</code>
            </dd>
          </div>
          <div className="detail-row">
            <dt>Email</dt>
            <dd>{env.email_backend}</dd>
          </div>
          <div className="detail-row">
            <dt>Server timezone</dt>
            <dd>{env.time_zone}</dd>
          </div>
        </dl>
      </section>
    </div>
  )
}
