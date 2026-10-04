import { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { getHealthDetails } from '../api/system'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'

const CHECK_LABELS = {
  database: 'Database',
  redis: 'Redis (Celery broker)',
  celery: 'Celery workers',
  storage: 'Media storage',
  ffmpeg: 'FFmpeg (video rendering)',
}

function CheckRow({ name, check }) {
  let detail = ''
  if (name === 'database') detail = check.ok ? `${check.vendor} · ${check.latency_ms} ms` : check.error
  if (name === 'redis') detail = check.ok ? `${check.latency_ms} ms` : check.error
  if (name === 'celery') detail = check.ok ? check.workers.join(', ') : check.error || 'No worker responded - start `celery -A config worker`'
  if (name === 'storage') detail = check.ok ? check.backend : `${check.backend}: ${check.error}`
  if (name === 'ffmpeg') detail = check.ok ? check.path : check.note
  return (
    <div className="health-row">
      <span className={`health-icon ${check.ok ? 'health-ok' : 'health-bad'}`} aria-hidden="true">
        {check.ok ? '✓' : '✗'}
      </span>
      <div>
        <strong>{CHECK_LABELS[name] || name}</strong>
        <div className="page-subtitle">
          {check.ok ? 'Healthy' : 'Problem'} {detail ? `· ${detail}` : ''}
        </div>
      </div>
    </div>
  )
}

export default function SystemHealthPage() {
  const { isAdmin } = useAuth()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setData(await getHealthDetails())
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load system health.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isAdmin) load()
  }, [isAdmin, load])

  if (!isAdmin) return <Navigate to="/client" replace />

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>System health</h1>
          <p className="page-subtitle">Live status of every service the platform depends on.</p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={load} disabled={loading}>
          {loading ? 'Checking…' : 'Re-check'}
        </button>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {data && (
        <>
          <div className={`alert ${data.status === 'ok' ? 'alert-success' : 'alert-warning'}`}>
            {data.status === 'ok' ? '✓ All systems operational.' : '⚠ Some services need attention - see below.'}
          </div>
          <div className="detail-grid detail-grid-even">
            <div className="card">
              <div className="card-header">
                <h2>Services</h2>
              </div>
              {Object.entries(data.checks).map(([name, check]) => (
                <CheckRow key={name} name={name} check={check} />
              ))}
            </div>
            <div className="card">
              <div className="card-header">
                <h2>Integrations</h2>
              </div>
              <dl className="detail-list">
                {Object.entries(data.ai).map(([kind, info]) => {
                  const credentials = data.ai_credentials[kind]?.[info.provider]
                  return (
                    <div className="detail-row" key={kind}>
                      <dt>AI {kind}</dt>
                      <dd>
                        {info.provider} · {info.model} {credentials ? (credentials.configured ? '✓ key set' : `✗ set ${credentials.env_vars.join(', ')}`) : ''}
                      </dd>
                    </div>
                  )
                })}
                <div className="detail-row">
                  <dt>Meta OAuth</dt>
                  <dd>{data.social_oauth.meta.configured ? '✓ configured' : '✗ META_APP_ID / META_APP_SECRET not set'}</dd>
                </div>
                <div className="detail-row">
                  <dt>LinkedIn OAuth</dt>
                  <dd>{data.social_oauth.linkedin.configured ? '✓ configured' : '✗ LINKEDIN_CLIENT_ID / SECRET not set'}</dd>
                </div>
                <div className="detail-row">
                  <dt>WhatsApp</dt>
                  <dd>
                    {data.whatsapp.provider} {data.whatsapp.provider === 'console' ? '(test mode - not delivering)' : data.whatsapp.configured ? '✓' : '✗ not configured'}
                  </dd>
                </div>
                <div className="detail-row">
                  <dt>Public media URL</dt>
                  <dd>
                    <code>{data.public_media_base_url}</code>
                  </dd>
                </div>
                <div className="detail-row">
                  <dt>Debug mode</dt>
                  <dd>{data.debug ? 'On (development)' : 'Off'}</dd>
                </div>
              </dl>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
