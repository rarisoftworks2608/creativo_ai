import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  connectSocialAccount,
  disconnectSocialAccount,
  listSocialAccounts,
  updateSocialAccount,
} from '../api/socialAccounts'
import { getCompany } from '../api/companies'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import Modal from '../components/Modal'

const PLATFORMS = [
  { value: 'instagram', label: 'Instagram' },
  { value: 'facebook', label: 'Facebook' },
  { value: 'linkedin', label: 'LinkedIn' },
]

const TOKEN_HELP = {
  instagram: 'Get a long-lived access token for the linked Instagram Business account from the Meta Developer Console (Graph API Explorer).',
  facebook: 'Get a Page access token from the Meta Developer Console (Graph API Explorer), scoped to the Page you want to publish to.',
  linkedin: 'Get an access token with the required organization/share scopes from the LinkedIn Developer Portal.',
}

const EMPTY_FORM = { platform: 'instagram', account_name: '', account_id: '', access_token: '', token_expires_at: '', notes: '' }

export default function SocialAccountsPage() {
  const { id: companyId } = useParams()
  const { isAdmin } = useAuth()

  const [company, setCompany] = useState(null)
  const [accounts, setAccounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [showConnect, setShowConnect] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [connecting, setConnecting] = useState(false)
  const [connectError, setConnectError] = useState('')

  const [editingAccount, setEditingAccount] = useState(null)
  const [editToken, setEditToken] = useState('')
  const [savingEdit, setSavingEdit] = useState(false)
  const [editError, setEditError] = useState('')

  const [disconnectingId, setDisconnectingId] = useState(null)

  const load = useCallback(async () => {
    if (!isAdmin) {
      setLoading(false)
      return
    }
    setLoading(true)
    setLoadError('')
    try {
      const [companyData, accountsData] = await Promise.all([getCompany(companyId), listSocialAccounts(companyId)])
      setCompany(companyData)
      setAccounts(accountsData.results)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load social accounts.'))
    } finally {
      setLoading(false)
    }
  }, [companyId, isAdmin])

  useEffect(() => {
    load()
  }, [load])

  function updateField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleConnect(event) {
    event.preventDefault()
    setConnecting(true)
    setConnectError('')
    try {
      const payload = { ...form, token_expires_at: form.token_expires_at || null }
      const created = await connectSocialAccount(companyId, payload)
      setAccounts((prev) => [created, ...prev])
      setShowConnect(false)
      setForm(EMPTY_FORM)
    } catch (err) {
      setConnectError(extractErrorMessage(err, 'Could not connect this account.'))
    } finally {
      setConnecting(false)
    }
  }

  function openEdit(account) {
    setEditingAccount({ ...account })
    setEditToken('')
    setEditError('')
  }

  async function handleSaveEdit(event) {
    event.preventDefault()
    setSavingEdit(true)
    setEditError('')
    try {
      const payload = { account_name: editingAccount.account_name, notes: editingAccount.notes }
      if (editToken) payload.access_token = editToken
      const updated = await updateSocialAccount(companyId, editingAccount.id, payload)
      setAccounts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
      setEditingAccount(null)
    } catch (err) {
      setEditError(extractErrorMessage(err, 'Could not save changes.'))
    } finally {
      setSavingEdit(false)
    }
  }

  async function handleDisconnect(accountId) {
    if (!window.confirm('Disconnect this account? It will need a fresh token to reconnect.')) return
    setDisconnectingId(accountId)
    try {
      const updated = await disconnectSocialAccount(companyId, accountId)
      setAccounts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not disconnect this account.'))
    } finally {
      setDisconnectingId(null)
    }
  }

  if (!isAdmin) {
    return <div className="alert alert-error">Social media account management is only available to admins.</div>
  }
  if (loading) return <div className="page-loading">Loading…</div>
  if (loadError && !company) return <div className="alert alert-error">{loadError}</div>
  if (!company) return null

  return (
    <div>
      <Link to={`/companies/${companyId}`} className="back-link">
        ← Back to {company.name}
      </Link>

      <div className="page-header">
        <div>
          <h1>Social Media Accounts</h1>
          <p className="page-subtitle">{company.name}</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowConnect(true)}>
          + Connect account
        </button>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      {accounts.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <p>No social accounts connected yet.</p>
          </div>
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Platform</th>
                <th>Account</th>
                <th>Token</th>
                <th>Expires</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => (
                <tr key={account.id}>
                  <td>{account.platform_display}</td>
                  <td>
                    {account.account_name}
                    {account.account_id && <div className="page-subtitle">{account.account_id}</div>}
                  </td>
                  <td>{account.has_token ? <code>{account.token_masked}</code> : <span className="muted">Not set</span>}</td>
                  <td>{account.token_expires_at ? new Date(account.token_expires_at).toLocaleDateString() : '—'}</td>
                  <td>
                    <span className={`badge badge-${account.status}`}>{account.status}</span>
                  </td>
                  <td className="table-actions">
                    <button type="button" className="btn-link" onClick={() => openEdit(account)}>
                      Edit
                    </button>
                    {account.status !== 'disconnected' && (
                      <button
                        type="button"
                        className="btn-link btn-link-danger"
                        disabled={disconnectingId === account.id}
                        onClick={() => handleDisconnect(account.id)}
                      >
                        Disconnect
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showConnect && (
        <Modal title="Connect social account" onClose={() => setShowConnect(false)}>
          <form onSubmit={handleConnect}>
            {connectError && <div className="alert alert-error">{connectError}</div>}
            <label className="field">
              <span>Platform *</span>
              <select value={form.platform} onChange={(e) => updateField('platform', e.target.value)} required>
                {PLATFORMS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Account name *</span>
              <input
                value={form.account_name}
                onChange={(e) => updateField('account_name', e.target.value)}
                placeholder="e.g. Acme Restaurant IG"
                required
              />
            </label>
            <label className="field">
              <span>Account / Page ID</span>
              <input value={form.account_id} onChange={(e) => updateField('account_id', e.target.value)} />
            </label>
            <label className="field">
              <span>Access token *</span>
              <textarea rows={3} value={form.access_token} onChange={(e) => updateField('access_token', e.target.value)} required />
            </label>
            <p className="modal-hint">{TOKEN_HELP[form.platform]}</p>
            <label className="field">
              <span>Token expires on</span>
              <input type="date" value={form.token_expires_at} onChange={(e) => updateField('token_expires_at', e.target.value)} />
            </label>
            <label className="field">
              <span>Notes</span>
              <textarea rows={2} value={form.notes} onChange={(e) => updateField('notes', e.target.value)} />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setShowConnect(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={connecting}>
                {connecting ? 'Connecting…' : 'Connect'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {editingAccount && (
        <Modal title={`Edit ${editingAccount.account_name}`} onClose={() => setEditingAccount(null)}>
          <form onSubmit={handleSaveEdit}>
            {editError && <div className="alert alert-error">{editError}</div>}
            <label className="field">
              <span>Account name</span>
              <input
                value={editingAccount.account_name}
                onChange={(e) => setEditingAccount((prev) => ({ ...prev, account_name: e.target.value }))}
              />
            </label>
            <label className="field">
              <span>Notes</span>
              <textarea
                rows={2}
                value={editingAccount.notes}
                onChange={(e) => setEditingAccount((prev) => ({ ...prev, notes: e.target.value }))}
              />
            </label>
            <label className="field">
              <span>Replace access token</span>
              <textarea rows={3} value={editToken} onChange={(e) => setEditToken(e.target.value)} placeholder="Leave blank to keep the current token" />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setEditingAccount(null)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={savingEdit}>
                {savingEdit ? 'Saving…' : 'Save'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
