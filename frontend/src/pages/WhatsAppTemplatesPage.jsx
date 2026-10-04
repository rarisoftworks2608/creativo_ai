import { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import {
  createWhatsAppTemplate,
  deleteWhatsAppTemplate,
  getWhatsAppStatus,
  listWhatsAppTemplates,
  syncWhatsAppTemplates,
  updateWhatsAppTemplate,
} from '../api/whatsapp'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import Modal from '../components/Modal'
import { formatDateTime } from '../utils/format'

const EVENTS = [
  ['approval_required', 'Content generated - approval required'],
  ['content_regenerated', 'Content regenerated'],
  ['content_approved', 'Content approved'],
  ['content_rejected', 'Content rejected'],
  ['content_published', 'Content published'],
  ['publishing_failed', 'Publishing failed'],
  ['approval_reminder', 'Approval reminder'],
  ['monthly_report', 'Monthly report ready'],
]
const VARIABLES = ['company_name', 'topic', 'scheduled_date', 'link', 'approved_by', 'feedback', 'platform', 'error', 'hours_waiting', 'period']
const EMPTY = { event: 'approval_required', name: '', language_code: 'en', category: 'utility', body: '', variables: [], is_active: true }

export default function WhatsAppTemplatesPage() {
  const { isAdmin } = useAuth()
  const [templates, setTemplates] = useState([])
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [editing, setEditing] = useState(null)
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [templateData, statusData] = await Promise.all([listWhatsAppTemplates(), getWhatsAppStatus()])
      setTemplates(templateData)
      setStatus(statusData)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load WhatsApp templates.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isAdmin) load()
  }, [isAdmin, load])

  if (!isAdmin) return <Navigate to="/client" replace />

  async function save(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = { ...editing }
      delete payload.id
      if (editing.id) await updateWhatsAppTemplate(editing.id, payload)
      else await createWhatsAppTemplate(payload)
      setEditing(null)
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save the template.'))
    } finally {
      setSaving(false)
    }
  }

  async function remove(template) {
    if (!window.confirm(`Delete the "${template.name}" mapping?`)) return
    try {
      await deleteWhatsAppTemplate(template.id)
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not delete.'))
    }
  }

  async function sync() {
    setSyncing(true)
    setError('')
    setNotice('')
    try {
      setTemplates(await syncWhatsAppTemplates())
      setNotice('Template statuses refreshed from WhatsApp Manager.')
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not sync templates.'))
    } finally {
      setSyncing(false)
    }
  }

  const placeholderCount = editing ? new Set((editing.body.match(/\{\{(\d+)\}\}/g) || [])).size : 0

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>WhatsApp templates</h1>
          <p className="page-subtitle">
            Business-initiated WhatsApp messages must use templates approved by Meta. Map each workflow event to one.
          </p>
        </div>
        <div className="header-actions">
          <button type="button" className="btn btn-ghost" onClick={sync} disabled={syncing}>
            {syncing ? 'Syncing…' : 'Sync status from Meta'}
          </button>
          <button type="button" className="btn btn-primary" onClick={() => setEditing({ ...EMPTY })}>
            + Template
          </button>
        </div>
      </div>

      {status && (
        <div className="card">
          <div className="card-header">
            <h2>WhatsApp Cloud API</h2>
            <span className={`badge ${status.configured && !status.is_console ? 'badge-active' : 'badge-expired'}`}>
              {status.is_console ? 'Test mode (console)' : status.configured ? 'Live' : 'Not configured'}
            </span>
          </div>
          <dl className="detail-list">
            <div className="detail-row">
              <dt>Provider</dt>
              <dd>{status.provider}</dd>
            </div>
            <div className="detail-row">
              <dt>Credentials</dt>
              <dd>
                Phone number ID {status.phone_number_id_set ? '✓' : '✗'} · Business account ID{' '}
                {status.business_account_id_set ? '✓' : '✗'} · Access token {status.access_token_set ? '✓' : '✗'}
              </dd>
            </div>
            <div className="detail-row">
              <dt>Webhook URL</dt>
              <dd>
                <code>{status.webhook_url}</code> {status.webhook_verify_token_set ? '(verify token set)' : '(set WHATSAPP_WEBHOOK_VERIFY_TOKEN)'}
              </dd>
            </div>
            <div className="detail-row">
              <dt>Last 7 days</dt>
              <dd>
                {status.last_7_days.sent} sent · {status.last_7_days.delivered} delivered · {status.last_7_days.read} read ·{' '}
                {status.last_7_days.failed} failed · {status.last_7_days.skipped} skipped
              </dd>
            </div>
          </dl>
        </div>
      )}

      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      {loading ? (
        <div className="page-loading">Loading…</div>
      ) : (
        <div className="card card-flush">
          <div className="table-wrapper">
            <table className="table table-stack">
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Template</th>
                  <th>Body</th>
                  <th>Meta status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {templates.map((template) => (
                  <tr key={template.id}>
                    <td data-label="Event">
                      {template.event_display}
                      {!template.is_active && <div className="page-subtitle">inactive</div>}
                    </td>
                    <td data-label="Template">
                      <code>{template.name}</code>
                      <div className="page-subtitle">
                        {template.language_code} · {template.category}
                      </div>
                    </td>
                    <td data-label="Body" className="cell-wrap">
                      {template.body}
                      <div className="page-subtitle">
                        {template.variables.map((v, i) => `{{${i + 1}}} = ${v}`).join(' · ')}
                      </div>
                    </td>
                    <td data-label="Meta status">
                      <span className={`badge status-badge meta-${template.meta_status}`}>{template.meta_status_display}</span>
                      {template.last_synced_at && <div className="page-subtitle">{formatDateTime(template.last_synced_at)}</div>}
                    </td>
                    <td className="table-actions">
                      <button type="button" className="btn-link" onClick={() => setEditing({ ...template })}>
                        Edit
                      </button>
                      <button type="button" className="btn-link btn-link-danger" onClick={() => remove(template)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {editing && (
        <Modal title={editing.id ? `Edit ${editing.name}` : 'New template mapping'} onClose={() => setEditing(null)} width={640}>
          <form onSubmit={save}>
            <div className="field-row">
              <label className="field">
                <span>Event</span>
                <select value={editing.event} onChange={(e) => setEditing({ ...editing, event: e.target.value })}>
                  {EVENTS.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Language code</span>
                <input value={editing.language_code} onChange={(e) => setEditing({ ...editing, language_code: e.target.value })} />
              </label>
            </div>
            <label className="field">
              <span>Template name (exactly as in WhatsApp Manager)</span>
              <input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} required pattern="[a-z0-9_]+" title="lowercase letters, numbers and underscores" />
            </label>
            <label className="field">
              <span>Body (with {'{{1}}'}, {'{{2}}'} … placeholders)</span>
              <textarea rows={4} value={editing.body} onChange={(e) => setEditing({ ...editing, body: e.target.value })} required />
            </label>
            <div className="field">
              <span>
                Fill placeholders with ({placeholderCount} placeholder{placeholderCount === 1 ? '' : 's'})
              </span>
              {Array.from({ length: placeholderCount }).map((_, index) => (
                <label key={index} className="inline-field">
                  {`{{${index + 1}}}`}
                  <select
                    value={editing.variables[index] || ''}
                    onChange={(e) => {
                      const variables = [...editing.variables]
                      variables[index] = e.target.value
                      setEditing({ ...editing, variables: variables.slice(0, placeholderCount) })
                    }}
                    required
                  >
                    <option value="">Choose…</option>
                    {VARIABLES.map((v) => (
                      <option key={v} value={v}>
                        {v}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <label className="field-checkbox">
              <input type="checkbox" checked={editing.is_active} onChange={(e) => setEditing({ ...editing, is_active: e.target.checked })} />
              Active
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
