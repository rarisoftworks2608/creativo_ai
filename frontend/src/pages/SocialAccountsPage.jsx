import { useCallback, useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import {
  connectSocialAccount,
  disconnectSocialAccount,
  getOAuthStatus,
  listSocialAccounts,
  refreshSocialToken,
  startOAuth,
  testSocialAccountConnection,
  updateSocialAccount,
} from '../api/socialAccounts'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useCompanyWorkspace } from '../context/CompanyWorkspaceContext'
import Modal from '../components/Modal'
import { formatCompact, formatDate, formatDateTime, timeAgo } from '../utils/format'
import { OAUTH_COMPANY_KEY } from '../utils/oauth'

const PLATFORMS = [
  { value: 'instagram', label: 'Instagram' },
  { value: 'facebook', label: 'Facebook' },
  { value: 'linkedin', label: 'LinkedIn' },
]

const TOKEN_HELP = {
  instagram:
    'Instagram professional account ID + its parent Facebook Page access token (Graph API Explorer → select the Page → copy the Page token).',
  facebook: 'Facebook Page ID + a Page access token with pages_manage_posts (Graph API Explorer → your app → Page token).',
  linkedin: 'Organization ID (or member ID) + an access token with w_organization_social (or w_member_social).',
}

const EMPTY_FORM = {
  platform: 'instagram', account_name: '', account_id: '', page_id: '', access_token: '', token_expires_at: '', notes: '',
}

export default function SocialAccountsPage() {
  const { id: companyId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const { isAdmin } = useAuth()
  const workspace = useCompanyWorkspace()

  const [accounts, setAccounts] = useState([])
  const [oauth, setOauth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [startingProvider, setStartingProvider] = useState('')

  const [showManual, setShowManual] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState(null)
  const [editToken, setEditToken] = useState('')
  const [showSetup, setShowSetup] = useState(null)

  const load = useCallback(async () => {
    if (!isAdmin) {
      setLoading(false)
      return
    }
    setError('')
    try {
      const [accountData, oauthData] = await Promise.all([listSocialAccounts(companyId), getOAuthStatus(companyId)])
      setAccounts(accountData.results)
      setOauth(oauthData)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load social accounts.'))
    } finally {
      setLoading(false)
    }
  }, [companyId, isAdmin])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const connected = searchParams.get('connected')
    if (connected) {
      setNotice(`Connected ${connected} account${connected === '1' ? '' : 's'}.`)
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, setSearchParams])

  if (!isAdmin) return <div className="alert alert-error">Social media account management is only available to admins.</div>
  if (loading) return <div className="page-loading">Loading…</div>

  async function beginOAuth(provider) {
    setStartingProvider(provider)
    setError('')
    try {
      const { authorization_url: url } = await startOAuth(companyId, provider)
      sessionStorage.setItem(OAUTH_COMPANY_KEY, companyId)
      window.location.assign(url)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not start the login.'))
      setStartingProvider('')
    }
  }

  async function act(account, action) {
    setBusyId(account.id)
    setError('')
    setNotice('')
    try {
      if (action === 'test') {
        const result = await testSocialAccountConnection(companyId, account.id)
        setAccounts((prev) => prev.map((a) => (a.id === result.account.id ? result.account : a)))
        setNotice(result.detail)
      } else if (action === 'refresh') {
        const result = await refreshSocialToken(companyId, account.id)
        setAccounts((prev) => prev.map((a) => (a.id === result.account.id ? result.account : a)))
        setNotice(result.detail)
      } else if (action === 'disconnect') {
        if (!window.confirm(`Disconnect ${account.account_name}? Scheduled posts to it will fail until it is reconnected.`)) return
        const updated = await disconnectSocialAccount(companyId, account.id)
        setAccounts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
      }
    } catch (err) {
      setError(extractErrorMessage(err, 'That action failed.'))
    } finally {
      setBusyId(null)
    }
  }

  async function saveManual(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = {
        platform: form.platform, account_name: form.account_name, account_id: form.account_id,
        access_token: form.access_token, token_expires_at: form.token_expires_at || null, notes: form.notes,
        metadata: {},
      }
      if (form.platform === 'instagram' && form.page_id) payload.metadata.page_id = form.page_id
      if (form.platform === 'linkedin') payload.metadata.account_type = form.page_id === 'person' ? 'person' : 'organization'
      const created = await connectSocialAccount(companyId, payload)
      setAccounts((prev) => [created, ...prev])
      setShowManual(false)
      setForm(EMPTY_FORM)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not connect this account.'))
    } finally {
      setSaving(false)
    }
  }

  async function saveEdit(event) {
    event.preventDefault()
    setSaving(true)
    try {
      const payload = { account_name: editing.account_name, notes: editing.notes }
      if (editToken) payload.access_token = editToken
      const updated = await updateSocialAccount(companyId, editing.id, payload)
      setAccounts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
      setEditing(null)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save changes.'))
    } finally {
      setSaving(false)
    }
  }

  const active = accounts.filter((a) => a.status !== 'disconnected')
  const disconnected = accounts.filter((a) => a.status === 'disconnected')

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Social accounts</h1>
          <p className="page-subtitle">
            {workspace?.company?.name ? `${workspace.company.name} · ` : ''}Connect the Instagram, Facebook and LinkedIn accounts content
            is published to.
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      <div className="connect-grid">
        <div className="card connect-card">
          <h2>Facebook & Instagram</h2>
          <p className="page-subtitle">Log in with Facebook, then pick the Pages and linked Instagram professional accounts to publish to.</p>
          <button type="button" className="btn btn-primary" disabled={!oauth?.meta.configured || startingProvider === 'meta'} onClick={() => beginOAuth('meta')}>
            {startingProvider === 'meta' ? 'Redirecting…' : 'Continue with Facebook'}
          </button>
          {!oauth?.meta.configured && (
            <button type="button" className="btn-link" onClick={() => setShowSetup('meta')}>
              Not set up yet - how to enable
            </button>
          )}
        </div>
        <div className="card connect-card">
          <h2>LinkedIn</h2>
          <p className="page-subtitle">Log in with LinkedIn, then pick the Company Page (or personal profile) to publish to.</p>
          <button type="button" className="btn btn-primary" disabled={!oauth?.linkedin.configured || startingProvider === 'linkedin'} onClick={() => beginOAuth('linkedin')}>
            {startingProvider === 'linkedin' ? 'Redirecting…' : 'Continue with LinkedIn'}
          </button>
          {!oauth?.linkedin.configured && (
            <button type="button" className="btn-link" onClick={() => setShowSetup('linkedin')}>
              Not set up yet - how to enable
            </button>
          )}
        </div>
        <div className="card connect-card connect-card-muted">
          <h2>Paste a token</h2>
          <p className="page-subtitle">Advanced: connect with an access token from the platform&apos;s developer tools.</p>
          <button type="button" className="btn btn-ghost" onClick={() => setShowManual(true)}>
            Connect manually
          </button>
        </div>
      </div>

      {active.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <p>No accounts connected yet.</p>
          </div>
        </div>
      ) : (
        <div className="account-grid">
          {active.map((account) => (
            <div className="card account-card" key={account.id}>
              <div className="account-card-head">
                {account.profile?.picture_url ? (
                  <img src={account.profile.picture_url} alt="" className="account-avatar" />
                ) : (
                  <span className="account-avatar account-avatar-empty">{account.platform_display[0]}</span>
                )}
                <div className="account-card-title">
                  <strong>{account.account_name}</strong>
                  <span className="page-subtitle">
                    {account.platform_display}
                    {account.profile?.account_type === 'organization' ? ' Company Page' : ''}
                    {account.profile?.username ? ` · @${account.profile.username}` : ''}
                  </span>
                </div>
                <span className={`badge badge-${account.status}`}>{account.status}</span>
              </div>
              <dl className="detail-list detail-list-compact">
                {account.profile?.followers_count !== undefined && (
                  <div className="detail-row">
                    <dt>Followers</dt>
                    <dd>{formatCompact(account.profile.followers_count)}</dd>
                  </div>
                )}
                {account.profile?.page_name && (
                  <div className="detail-row">
                    <dt>Facebook Page</dt>
                    <dd>{account.profile.page_name}</dd>
                  </div>
                )}
                <div className="detail-row">
                  <dt>Connected</dt>
                  <dd>
                    {account.connection_method === 'oauth' ? 'OAuth login' : 'Manual token'} · {formatDate(account.created_at)}
                  </dd>
                </div>
                <div className="detail-row">
                  <dt>Token</dt>
                  <dd>
                    {account.has_token ? <code>{account.token_masked}</code> : 'Not set'}
                    {account.token_expires_at ? ` · expires ${formatDate(account.token_expires_at)}` : account.has_token ? ' · no expiry' : ''}
                  </dd>
                </div>
                {account.scopes?.length > 0 && (
                  <div className="detail-row">
                    <dt>Permissions</dt>
                    <dd className="scope-list">{account.scopes.join(', ')}</dd>
                  </div>
                )}
                {account.last_checked_at && (
                  <div className="detail-row">
                    <dt>Last checked</dt>
                    <dd>{timeAgo(account.last_checked_at)}</dd>
                  </div>
                )}
              </dl>
              {account.last_error && <div className="alert alert-error job-error">{account.last_error}</div>}
              <div className="account-actions">
                <button type="button" className="btn btn-ghost btn-sm" disabled={busyId === account.id} onClick={() => act(account, 'test')}>
                  {busyId === account.id ? 'Working…' : 'Test connection'}
                </button>
                {account.has_refresh_token && (
                  <button type="button" className="btn btn-ghost btn-sm" disabled={busyId === account.id} onClick={() => act(account, 'refresh')}>
                    Refresh token
                  </button>
                )}
                {account.status === 'expired' && account.platform !== 'linkedin' && oauth?.meta.configured && (
                  <button type="button" className="btn btn-primary btn-sm" onClick={() => beginOAuth('meta')}>
                    Reconnect
                  </button>
                )}
                <button
                  type="button"
                  className="btn-link"
                  onClick={() => {
                    setEditing({ ...account })
                    setEditToken('')
                  }}
                >
                  Edit
                </button>
                <button type="button" className="btn-link btn-link-danger" disabled={busyId === account.id} onClick={() => act(account, 'disconnect')}>
                  Disconnect
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {disconnected.length > 0 && (
        <details className="card">
          <summary>Disconnected accounts ({disconnected.length})</summary>
          <ul className="plain-list">
            {disconnected.map((account) => (
              <li key={account.id}>
                {account.platform_display} · {account.account_name} · disconnected {formatDateTime(account.updated_at)}
              </li>
            ))}
          </ul>
        </details>
      )}

      {showSetup && oauth && (
        <Modal title={showSetup === 'meta' ? 'Enable “Continue with Facebook”' : 'Enable “Continue with LinkedIn”'} onClose={() => setShowSetup(null)} width={640}>
          {showSetup === 'meta' ? (
            <ol className="setup-steps">
              <li>Create a Meta app (type Business) at developers.facebook.com and add “Facebook Login for Business”.</li>
              <li>
                Add this Valid OAuth Redirect URI: <code>{oauth.meta.redirect_uri}</code>
              </li>
              <li>
                Put the app ID and secret in the backend <code>.env</code> as <code>META_APP_ID</code> and <code>META_APP_SECRET</code>, then
                restart the backend.
              </li>
              <li>Request these permissions in App Review before going live: {oauth.meta.scopes.join(', ')}.</li>
            </ol>
          ) : (
            <ol className="setup-steps">
              <li>Create an app at linkedin.com/developers, linked to your LinkedIn Company Page.</li>
              <li>Add the products “Sign In with LinkedIn using OpenID Connect”, “Share on LinkedIn” and (for Company Pages) “Community Management API”.</li>
              <li>
                Add this Authorized redirect URL: <code>{oauth.linkedin.redirect_uri}</code>
              </li>
              <li>
                Put the client ID and secret in the backend <code>.env</code> as <code>LINKEDIN_CLIENT_ID</code> and{' '}
                <code>LINKEDIN_CLIENT_SECRET</code>, then restart the backend.
              </li>
            </ol>
          )}
          <p className="modal-hint">The full step-by-step guide is in docs/meta-setup-guide.md and docs/linkedin-setup-guide.md.</p>
        </Modal>
      )}

      {showManual && (
        <Modal title="Connect with an access token" onClose={() => setShowManual(false)}>
          <form onSubmit={saveManual}>
            <div className="field-row">
              <label className="field">
                <span>Platform *</span>
                <select value={form.platform} onChange={(e) => setForm((f) => ({ ...f, platform: e.target.value }))}>
                  {PLATFORMS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Account name *</span>
                <input value={form.account_name} onChange={(e) => setForm((f) => ({ ...f, account_name: e.target.value }))} required />
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                <span>{form.platform === 'facebook' ? 'Page ID *' : form.platform === 'instagram' ? 'Instagram account ID *' : 'Organization / member ID *'}</span>
                <input value={form.account_id} onChange={(e) => setForm((f) => ({ ...f, account_id: e.target.value }))} required />
              </label>
              {form.platform === 'instagram' && (
                <label className="field">
                  <span>Parent Facebook Page ID</span>
                  <input value={form.page_id} onChange={(e) => setForm((f) => ({ ...f, page_id: e.target.value }))} />
                </label>
              )}
              {form.platform === 'linkedin' && (
                <label className="field">
                  <span>Posts as</span>
                  <select value={form.page_id || 'organization'} onChange={(e) => setForm((f) => ({ ...f, page_id: e.target.value }))}>
                    <option value="organization">Company Page</option>
                    <option value="person">Personal profile</option>
                  </select>
                </label>
              )}
            </div>
            <label className="field">
              <span>Access token *</span>
              <textarea rows={3} value={form.access_token} onChange={(e) => setForm((f) => ({ ...f, access_token: e.target.value }))} required />
            </label>
            <p className="modal-hint">{TOKEN_HELP[form.platform]}</p>
            <label className="field">
              <span>Token expires on</span>
              <input type="date" value={form.token_expires_at} onChange={(e) => setForm((f) => ({ ...f, token_expires_at: e.target.value }))} />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setShowManual(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Connecting…' : 'Connect'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {editing && (
        <Modal title={`Edit ${editing.account_name}`} onClose={() => setEditing(null)}>
          <form onSubmit={saveEdit}>
            <label className="field">
              <span>Account name</span>
              <input value={editing.account_name} onChange={(e) => setEditing((a) => ({ ...a, account_name: e.target.value }))} />
            </label>
            <label className="field">
              <span>Notes</span>
              <textarea rows={2} value={editing.notes} onChange={(e) => setEditing((a) => ({ ...a, notes: e.target.value }))} />
            </label>
            <label className="field">
              <span>Replace access token</span>
              <textarea rows={3} value={editToken} onChange={(e) => setEditToken(e.target.value)} placeholder="Leave blank to keep the current token" />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                Save
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
