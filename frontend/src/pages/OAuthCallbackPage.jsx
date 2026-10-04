import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { completeOAuth, connectOAuthAccounts } from '../api/socialAccounts'
import { extractErrorMessage } from '../api/client'
import { formatCompact, platformLabel } from '../utils/format'
import { OAUTH_COMPANY_KEY } from '../utils/oauth'

/**
 * Where Meta / LinkedIn send the browser back after login. Exchanges the code for the
 * accounts that login can manage, then lets the admin pick which Pages / Instagram
 * accounts / LinkedIn organizations to connect (Epic 10: Page / Organization selection).
 */
export default function OAuthCallbackPage() {
  const { provider } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const companyId = sessionStorage.getItem(OAUTH_COMPANY_KEY)

  const [stage, setStage] = useState('exchanging')
  const [error, setError] = useState('')
  const [session, setSession] = useState(null)
  const [selected, setSelected] = useState([])
  const [connecting, setConnecting] = useState(false)
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    const providerError = searchParams.get('error_description') || searchParams.get('error_message') || searchParams.get('error')
    const code = searchParams.get('code')
    const state = searchParams.get('state')
    if (providerError) {
      setError(`The login was cancelled or refused: ${providerError}`)
      setStage('error')
      return
    }
    if (!code || !state || !companyId) {
      setError('This page was opened without a valid login response. Start again from the company’s Social accounts page.')
      setStage('error')
      return
    }
    completeOAuth(companyId, provider, code, state)
      .then((data) => {
        setSession(data)
        setSelected(data.candidates.filter((c) => !c.already_connected).map((c) => c.key))
        setStage('choose')
      })
      .catch((err) => {
        setError(extractErrorMessage(err, 'Could not finish connecting.'))
        setStage('error')
      })
  }, [companyId, provider, searchParams])

  function toggle(key) {
    setSelected((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]))
  }

  async function connect() {
    setConnecting(true)
    setError('')
    try {
      await connectOAuthAccounts(companyId, session.session_id, selected)
      sessionStorage.removeItem(OAUTH_COMPANY_KEY)
      navigate(`/companies/${companyId}/social-accounts?connected=${selected.length}`, { replace: true })
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not connect the selected accounts.'))
    } finally {
      setConnecting(false)
    }
  }

  const providerName = provider === 'meta' ? 'Facebook & Instagram' : 'LinkedIn'

  return (
    <div className="oauth-page">
      <div className="card oauth-card">
        <h1>Connect {providerName}</h1>
        {stage === 'exchanging' && <p className="page-subtitle">Finishing the login and finding your accounts…</p>}
        {error && <div className="alert alert-error">{error}</div>}
        {stage === 'error' && companyId && (
          <Link to={`/companies/${companyId}/social-accounts`} className="btn btn-ghost">
            Back to social accounts
          </Link>
        )}
        {stage === 'choose' && session && (
          <>
            {session.warnings.map((warning) => (
              <div className="alert alert-warning" key={warning}>
                {warning}
              </div>
            ))}
            {session.candidates.length > 0 && (
              <>
                <p className="page-subtitle">Choose which accounts this company should publish to:</p>
                <div className="account-picker">
                  {session.candidates.map((candidate) => (
                    <label key={candidate.key} className={`account-option ${selected.includes(candidate.key) ? 'account-option-on' : ''}`}>
                      <input type="checkbox" checked={selected.includes(candidate.key)} onChange={() => toggle(candidate.key)} />
                      {candidate.picture_url ? (
                        <img src={candidate.picture_url} alt="" className="account-avatar" />
                      ) : (
                        <span className="account-avatar account-avatar-empty">{candidate.name?.[0] || '?'}</span>
                      )}
                      <span>
                        <strong>{candidate.name}</strong>
                        <span className="page-subtitle">
                          {' '}
                          {platformLabel(candidate.platform)}
                          {candidate.metadata?.account_type === 'organization' ? ' Company Page' : ''}
                          {candidate.metadata?.account_type === 'person' ? ' personal profile' : ''}
                          {candidate.username ? ` · @${candidate.username}` : ''}
                          {candidate.followers_count ? ` · ${formatCompact(candidate.followers_count)} followers` : ''}
                          {candidate.already_connected ? ' · already connected (will refresh token)' : ''}
                        </span>
                      </span>
                    </label>
                  ))}
                </div>
                <div className="modal-actions">
                  <Link to={`/companies/${companyId}/social-accounts`} className="btn btn-ghost">
                    Cancel
                  </Link>
                  <button type="button" className="btn btn-primary" onClick={connect} disabled={connecting || selected.length === 0}>
                    {connecting ? 'Connecting…' : `Connect ${selected.length} account${selected.length === 1 ? '' : 's'}`}
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}
