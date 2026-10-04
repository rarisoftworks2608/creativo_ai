import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import {
  createWhatsAppGroup,
  deactivateWhatsAppGroup,
  getWhatsAppConfig,
  getWhatsAppStatus,
  listWhatsAppMessages,
  resendWhatsAppMessage,
  sendWhatsAppTest,
  updateWhatsAppConfig,
} from '../api/whatsapp'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useCompanyWorkspace } from '../context/CompanyWorkspaceContext'
import { formatDateTime } from '../utils/format'

const AUDIENCE_LABELS = { all: 'Client + team', internal: 'Team only', clients: 'Client only' }
const LANGUAGES = [
  { value: 'en', label: 'English (en)' },
  { value: 'en_US', label: 'English US (en_US)' },
  { value: 'hi', label: 'Hindi (hi)' },
  { value: 'mr', label: 'Marathi (mr)' },
]

function NumberList({ label, value, onChange, placeholderName }) {
  function update(index, field, fieldValue) {
    onChange(value.map((entry, i) => (i === index ? { ...entry, [field]: fieldValue } : entry)))
  }
  return (
    <div className="field">
      <span>{label}</span>
      {value.length === 0 && <p className="field-hint-inline">None added yet.</p>}
      {value.map((entry, index) => (
        <div className="number-row" key={index}>
          <input value={entry.name} placeholder={placeholderName} onChange={(e) => update(index, 'name', e.target.value)} />
          <input value={entry.phone} placeholder="+91 98765 43210" inputMode="tel" onChange={(e) => update(index, 'phone', e.target.value)} />
          <button type="button" className="btn-link btn-link-danger" onClick={() => onChange(value.filter((_, i) => i !== index))}>
            Remove
          </button>
        </div>
      ))}
      <button type="button" className="btn btn-ghost btn-sm" onClick={() => onChange([...value, { name: '', phone: '' }])}>
        + Add number
      </button>
    </div>
  )
}

export default function WhatsAppPage() {
  const { id: companyId } = useParams()
  const { isAdmin } = useAuth()
  const workspace = useCompanyWorkspace()

  const [config, setConfig] = useState(null)
  const [status, setStatus] = useState(null)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [testPhone, setTestPhone] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [configData, statusData, messageData] = await Promise.all([
        getWhatsAppConfig(companyId),
        getWhatsAppStatus(),
        listWhatsAppMessages(companyId),
      ])
      setConfig(configData)
      setStatus(statusData)
      setMessages(messageData.results)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load WhatsApp settings.'))
    } finally {
      setLoading(false)
    }
  }, [companyId])

  useEffect(() => {
    if (isAdmin) load()
  }, [isAdmin, load])

  if (!isAdmin) return <Navigate to="/client" replace />
  if (loading) return <div className="page-loading">Loading…</div>
  if (!config) return <div className="alert alert-error">{error}</div>

  function update(field, value) {
    setConfig((prev) => ({ ...prev, [field]: value }))
  }

  function toggleEvent(event) {
    const events = config.enabled_events.includes(event)
      ? config.enabled_events.filter((e) => e !== event)
      : [...config.enabled_events, event]
    update('enabled_events', events)
  }

  async function save(event) {
    event?.preventDefault()
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const saved = await updateWhatsAppConfig(companyId, {
        is_enabled: config.is_enabled,
        business_number: config.business_number,
        client_numbers: config.client_numbers.filter((n) => n.phone.trim()),
        internal_numbers: config.internal_numbers.filter((n) => n.phone.trim()),
        include_client_users: config.include_client_users,
        enabled_events: config.enabled_events,
        language_code: config.language_code,
        group_name: config.group_name,
        group_description: config.group_description,
        group_invite_link: config.group_invite_link,
      })
      setConfig(saved)
      setNotice('WhatsApp settings saved.')
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save.'))
    } finally {
      setSaving(false)
    }
  }

  async function createGroup() {
    setError('')
    try {
      await save()
      const saved = await createWhatsAppGroup(companyId, {
        group_name: config.group_name || `${workspace?.company?.name || 'Client'} × Marketing`,
        group_description: config.group_description,
        group_invite_link: config.group_invite_link,
      })
      setConfig(saved)
      setNotice('Notification group is active - every enabled event now goes to its members.')
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not create the group.'))
    }
  }

  async function deactivateGroup() {
    if (!window.confirm('Deactivate the group? WhatsApp notifications for this company stop until it is re-activated.')) return
    try {
      setConfig(await deactivateWhatsAppGroup(companyId))
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not deactivate the group.'))
    }
  }

  async function sendTest(event) {
    event.preventDefault()
    setError('')
    setNotice('')
    try {
      await sendWhatsAppTest(companyId, testPhone)
      setNotice('Test message queued - check the delivery log below.')
      setMessages((await listWhatsAppMessages(companyId)).results)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not send the test message.'))
    }
  }

  async function resend(message) {
    try {
      await resendWhatsAppMessage(companyId, message.id)
      setMessages((await listWhatsAppMessages(companyId)).results)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not resend.'))
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>WhatsApp automation</h1>
          <p className="page-subtitle">
            {workspace?.company?.name ? `${workspace.company.name} · ` : ''}Approval requests, reminders, publishing updates and
            monthly reports on WhatsApp.
          </p>
        </div>
        <Link to="/whatsapp" className="btn btn-ghost">
          Templates & API status
        </Link>
      </div>

      {status?.is_console && (
        <div className="alert alert-info">
          WhatsApp is in <strong>test mode</strong> (WHATSAPP_PROVIDER=console): messages are logged below but not delivered.
          Add the WhatsApp Cloud API credentials in the backend .env and set WHATSAPP_PROVIDER=meta to go live.
        </div>
      )}
      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      <form onSubmit={save}>
        <div className="detail-grid detail-grid-even">
          <div className="card">
            <div className="card-header">
              <h2>Configuration</h2>
              <label className="switch">
                <input type="checkbox" checked={config.is_enabled} onChange={(e) => update('is_enabled', e.target.checked)} />
                <span>{config.is_enabled ? 'Enabled' : 'Disabled'}</span>
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                <span>Business number (sender)</span>
                <input value={config.business_number} placeholder="+91 …" onChange={(e) => update('business_number', e.target.value)} />
              </label>
              <label className="field">
                <span>Template language</span>
                <select value={config.language_code} onChange={(e) => update('language_code', e.target.value)}>
                  {LANGUAGES.map((l) => (
                    <option key={l.value} value={l.value}>
                      {l.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="field">
              <span>Send WhatsApp for</span>
              <div className="event-list">
                {config.available_events.map((event) => (
                  <label key={event.value} className="field-checkbox field-checkbox-inline event-option">
                    <input type="checkbox" checked={config.enabled_events.includes(event.value)} onChange={() => toggleEvent(event.value)} />
                    <span>
                      {event.label} <em className="muted">· {AUDIENCE_LABELS[event.audience]}</em>
                    </span>
                  </label>
                ))}
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h2>Notification group</h2>
              <span className={`badge ${config.group_status === 'active' ? 'badge-active' : 'badge-inactive'}`}>
                {config.group_status_display}
              </span>
            </div>
            <label className="field">
              <span>Group name</span>
              <input value={config.group_name} placeholder={`${workspace?.company?.name || 'Client'} × Marketing`} onChange={(e) => update('group_name', e.target.value)} />
            </label>
            <NumberList label="Client numbers" value={config.client_numbers} onChange={(v) => update('client_numbers', v)} placeholderName="Client contact" />
            <NumberList label="Internal team numbers" value={config.internal_numbers} onChange={(v) => update('internal_numbers', v)} placeholderName="Account manager" />
            <label className="field-checkbox">
              <input type="checkbox" checked={config.include_client_users} onChange={(e) => update('include_client_users', e.target.checked)} />
              Also include client logins who enabled WhatsApp in their settings
            </label>
            <label className="field">
              <span>WhatsApp group invite link (optional)</span>
              <input value={config.group_invite_link} placeholder="https://chat.whatsapp.com/…" onChange={(e) => update('group_invite_link', e.target.value)} />
              <span className="field-hint-inline">
                Messages are delivered to each member individually. For free-form chat, create a group in the WhatsApp app and
                paste its invite link here for reference.
              </span>
            </label>
            <div className="modal-actions">
              {config.group_status === 'active' ? (
                <button type="button" className="btn btn-ghost btn-danger-outline" onClick={deactivateGroup}>
                  Deactivate group
                </button>
              ) : (
                <button type="button" className="btn btn-ghost" onClick={createGroup}>
                  Create group
                </button>
              )}
            </div>
            <div className="recipients">
              <span className="recipients-title">Current recipients ({config.recipients.length})</span>
              {config.recipients.map((r) => (
                <span key={r.phone} className="tag-chip tag-chip-static">
                  {r.name || 'Unnamed'} · +{r.phone} · {r.type}
                </span>
              ))}
            </div>
          </div>
        </div>
        <div className="form-footer">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving…' : 'Save WhatsApp settings'}
          </button>
        </div>
      </form>

      <div className="card">
        <div className="card-header card-header-wrap">
          <h2>Delivery log</h2>
          <form className="inline-form" onSubmit={sendTest}>
            <input value={testPhone} placeholder="Test number +91…" inputMode="tel" onChange={(e) => setTestPhone(e.target.value)} required />
            <button type="submit" className="btn btn-ghost">
              Send test
            </button>
          </form>
        </div>
        {messages.length === 0 ? (
          <div className="empty-state">
            <p>No WhatsApp messages yet.</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="table table-stack">
              <thead>
                <tr>
                  <th>Sent</th>
                  <th>To</th>
                  <th>Event</th>
                  <th>Message</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {messages.map((message) => (
                  <tr key={message.id}>
                    <td data-label="Sent">{formatDateTime(message.sent_at || message.created_at)}</td>
                    <td data-label="To">
                      {message.recipient_name || '—'}
                      <div className="page-subtitle">+{message.to_number}</div>
                    </td>
                    <td data-label="Event">{message.event.replace(/_/g, ' ')}</td>
                    <td data-label="Message" className="cell-wrap">
                      {message.body}
                      {message.error && <div className="cell-error">{message.error}</div>}
                    </td>
                    <td data-label="Status">
                      <span className={`badge status-badge wa-status-${message.status}`}>{message.status_display}</span>
                    </td>
                    <td className="table-actions">
                      {['failed', 'skipped'].includes(message.status) && message.template_name && (
                        <button type="button" className="btn-link" onClick={() => resend(message)}>
                          Resend
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
