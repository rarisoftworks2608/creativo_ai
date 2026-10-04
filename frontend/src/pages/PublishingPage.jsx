import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  cancelPublishJob,
  createPublishJobs,
  getPublishPreview,
  getPublishingStats,
  getReadyToPublish,
  listPublishJobs,
  publishJobNow,
  retryPublishJob,
  updatePublishJob,
} from '../api/publishing'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useCompanyWorkspace } from '../context/CompanyWorkspaceContext'
import KpiTile from '../components/KpiTile'
import Modal from '../components/Modal'
import Tabs from '../components/Tabs'
import { formatDate, formatDateTime, formatNumber, platformLabel, toLocalInputValue } from '../utils/format'

const QUEUE_STATUSES = 'scheduled,queued,processing'

export default function PublishingPage() {
  const { id: companyId } = useParams()
  const { isAdmin } = useAuth()
  const workspace = useCompanyWorkspace()

  const [tab, setTab] = useState(isAdmin ? 'ready' : 'queue')
  const [stats, setStats] = useState(null)
  const [ready, setReady] = useState([])
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busyId, setBusyId] = useState(null)

  const [scheduling, setScheduling] = useState(null)
  const [rescheduling, setRescheduling] = useState(null)
  const [rescheduleAt, setRescheduleAt] = useState('')
  const [expandedLog, setExpandedLog] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const statsData = await getPublishingStats(companyId)
      setStats(statsData)
      if (tab === 'ready') {
        const data = await getReadyToPublish(companyId)
        setReady(data.results)
      } else {
        const status = { queue: QUEUE_STATUSES, published: 'published', failed: 'failed,cancelled' }[tab]
        const data = await listPublishJobs(companyId, { status, upcoming: tab === 'queue' ? 'true' : undefined })
        setJobs(data.results)
      }
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load publishing.'))
    } finally {
      setLoading(false)
    }
  }, [companyId, tab])

  useEffect(() => {
    load()
  }, [load])

  // Queue items move on their own (dispatcher runs every minute) - keep the view fresh.
  useEffect(() => {
    if (tab !== 'queue') return undefined
    const timer = setInterval(load, 20000)
    return () => clearInterval(timer)
  }, [tab, load])

  async function runAction(job, action) {
    setBusyId(job.id)
    setError('')
    setNotice('')
    try {
      if (action === 'cancel') await cancelPublishJob(companyId, job.id)
      if (action === 'retry') await retryPublishJob(companyId, job.id)
      if (action === 'now') await publishJobNow(companyId, job.id)
      setNotice(action === 'cancel' ? 'Post cancelled.' : 'Sent to the publishing queue - it goes out within a minute.')
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'That action failed.'))
    } finally {
      setBusyId(null)
    }
  }

  async function submitReschedule(event) {
    event.preventDefault()
    setBusyId(rescheduling.id)
    try {
      await updatePublishJob(companyId, rescheduling.id, { scheduled_at: new Date(rescheduleAt).toISOString() })
      setRescheduling(null)
      setNotice('Rescheduled.')
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not reschedule.'))
    } finally {
      setBusyId(null)
    }
  }

  const tabs = [
    ...(isAdmin ? [{ value: 'ready', label: 'Ready to publish', count: stats?.ready_to_publish }] : []),
    { value: 'queue', label: 'Scheduled', count: stats ? stats.scheduled + stats.processing : undefined },
    { value: 'published', label: 'Published', count: stats?.published },
    { value: 'failed', label: 'Failed / cancelled', count: stats ? stats.failed + stats.cancelled : undefined },
  ]

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Publishing</h1>
          <p className="page-subtitle">
            {workspace?.company?.name ? `${workspace.company.name} · ` : ''}Schedule approved content to Instagram, Facebook and
            LinkedIn, and track every post.
          </p>
        </div>
        {isAdmin && (
          <Link to={`/companies/${companyId}/social-accounts`} className="btn btn-ghost">
            Social accounts
          </Link>
        )}
      </div>

      {stats && (
        <div className="kpi-grid">
          <KpiTile label="Published this month" value={formatNumber(stats.published_this_month)} />
          <KpiTile label="Scheduled" value={formatNumber(stats.scheduled)} hint={stats.next_scheduled_at ? `Next: ${formatDateTime(stats.next_scheduled_at)}` : 'Nothing scheduled'} />
          <KpiTile label="Failed" value={formatNumber(stats.failed)} hint={stats.failed ? 'Retry from the Failed tab' : 'All clear'} />
          {isAdmin && <KpiTile label="Ready to publish" value={formatNumber(stats.ready_to_publish)} hint="Approved, not yet scheduled" />}
        </div>
      )}

      <Tabs tabs={tabs} value={tab} onChange={setTab} ariaLabel="Publishing sections" />
      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      {loading ? (
        <div className="page-loading">Loading…</div>
      ) : tab === 'ready' ? (
        ready.length === 0 ? (
          <div className="card">
            <div className="empty-state">
              <p>No approved content waiting. Approved items appear here until they&apos;re scheduled.</p>
              <Link to={`/companies/${companyId}/approvals`} className="btn btn-ghost">
                Go to approvals
              </Link>
            </div>
          </div>
        ) : (
          <div className="ready-grid">
            {ready.map((item) => {
              const thumb =
                item.latest_video_request?.thumbnail ||
                item.latest_generation_request?.variations?.find((v) => v.is_selected)?.image ||
                item.latest_generation_request?.variations?.[0]?.image
              return (
                <div className="card ready-card" key={item.id}>
                  {thumb ? <img src={thumb} alt="" className="ready-thumb" /> : <div className="ready-thumb ready-thumb-empty">No preview</div>}
                  <div className="ready-body">
                    <h2>{item.topic}</h2>
                    <p className="page-subtitle">
                      {item.content_type} · planned {formatDate(item.scheduled_date)}
                      {item.scheduled_time ? ` ${item.scheduled_time.slice(0, 5)}` : ''}
                    </p>
                    <p className="page-subtitle">{(item.platforms || []).map(platformLabel).join(', ')}</p>
                    <button type="button" className="btn btn-primary btn-block" onClick={() => setScheduling(item)}>
                      Schedule / publish
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )
      ) : jobs.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <p>{tab === 'queue' ? 'Nothing scheduled.' : tab === 'published' ? 'Nothing published yet.' : 'No failed posts.'}</p>
          </div>
        </div>
      ) : (
        <div className="job-list">
          {jobs.map((job) => (
            <div className="card job-card" key={job.id}>
              <div className="job-media">
                {job.media_preview?.[0] ? (
                  job.media_preview[0].kind === 'video' ? (
                    <div className="job-thumb job-thumb-video">▶</div>
                  ) : (
                    <img src={job.media_preview[0].url} alt="" className="job-thumb" />
                  )
                ) : (
                  <div className="job-thumb job-thumb-video">Aa</div>
                )}
              </div>
              <div className="job-main">
                <div className="job-title-row">
                  <strong>{job.topic || job.caption.slice(0, 60) || `Post #${job.id}`}</strong>
                  <span className={`badge status-badge pub-status-${job.status}`}>{job.status_display}</span>
                </div>
                <div className="page-subtitle">
                  {job.platform_display} · {job.account_name} · {job.post_type_display}
                </div>
                <div className="job-meta">
                  {job.status === 'published'
                    ? `Published ${formatDateTime(job.published_at)}`
                    : `${job.status === 'scheduled' ? 'Scheduled for' : 'Planned'} ${formatDateTime(job.scheduled_at)}`}
                  {job.attempts > 0 && job.status !== 'published' ? ` · attempt ${job.attempts}/${job.max_attempts}` : ''}
                </div>
                {job.last_error && job.status !== 'published' && <div className="alert alert-error job-error">{job.last_error}</div>}
                {job.error_log?.length > 0 && (
                  <button type="button" className="btn-link" onClick={() => setExpandedLog(expandedLog === job.id ? null : job.id)}>
                    {expandedLog === job.id ? 'Hide' : 'Show'} error log ({job.error_log.length})
                  </button>
                )}
                {expandedLog === job.id && (
                  <ul className="plain-list error-log">
                    {job.error_log.map((entry, index) => (
                      <li key={index}>
                        {formatDateTime(entry.at)} · attempt {entry.attempt}: {entry.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="job-actions">
                {job.external_url && (
                  <a href={job.external_url} target="_blank" rel="noreferrer" className="btn btn-ghost">
                    View post ↗
                  </a>
                )}
                {isAdmin && job.status === 'scheduled' && (
                  <>
                    <button type="button" className="btn btn-ghost" disabled={busyId === job.id} onClick={() => runAction(job, 'now')}>
                      Publish now
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={() => {
                        setRescheduling(job)
                        setRescheduleAt(toLocalInputValue(job.scheduled_at))
                      }}
                    >
                      Reschedule
                    </button>
                  </>
                )}
                {isAdmin && job.can_cancel && (
                  <button type="button" className="btn-link btn-link-danger" disabled={busyId === job.id} onClick={() => runAction(job, 'cancel')}>
                    Cancel
                  </button>
                )}
                {isAdmin && job.can_retry && (
                  <button type="button" className="btn btn-primary" disabled={busyId === job.id} onClick={() => runAction(job, 'retry')}>
                    {busyId === job.id ? 'Retrying…' : 'Retry'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {scheduling && (
        <ScheduleModal
          companyId={companyId}
          item={scheduling}
          onClose={() => setScheduling(null)}
          onDone={async (message) => {
            setScheduling(null)
            setNotice(message)
            setTab('queue')
            await load()
          }}
        />
      )}

      {rescheduling && (
        <Modal title="Reschedule post" onClose={() => setRescheduling(null)}>
          <form onSubmit={submitReschedule}>
            <label className="field">
              <span>New date & time (your local time)</span>
              <input type="datetime-local" value={rescheduleAt} onChange={(e) => setRescheduleAt(e.target.value)} required />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setRescheduling(null)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={busyId === rescheduling.id}>
                Save
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}

function ScheduleModal({ companyId, item, onClose, onDone }) {
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState([])
  const [caption, setCaption] = useState('')
  const [mode, setMode] = useState('schedule')
  const [when, setWhen] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getPublishPreview(companyId, item.id)
      .then((data) => {
        setPreview(data)
        setCaption(data.caption)
        setWhen(toLocalInputValue(data.suggested_publish_at))
        setSelected(data.accounts.filter((a) => a.suggested && a.status === 'connected').map((a) => a.id))
      })
      .catch((err) => setError(extractErrorMessage(err, 'Could not load the post preview.')))
  }, [companyId, item.id])

  function toggle(accountId) {
    setSelected((prev) => (prev.includes(accountId) ? prev.filter((id) => id !== accountId) : [...prev, accountId]))
  }

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = { content_calendar_item: item.id, social_account_ids: selected }
      if (caption !== preview.caption) payload.caption = caption
      if (mode === 'schedule') payload.scheduled_at = new Date(when).toISOString()
      const jobs = await createPublishJobs(companyId, payload)
      onDone(mode === 'now' ? `Publishing to ${jobs.length} account(s) now.` : `Scheduled to ${jobs.length} account(s).`)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not schedule this post.'))
    } finally {
      setSaving(false)
    }
  }

  const connected = preview?.accounts.filter((a) => a.status === 'connected') || []

  return (
    <Modal title={`Publish “${item.topic}”`} onClose={onClose} width={720}>
      {error && <div className="alert alert-error">{error}</div>}
      {!preview && !error && <div className="page-loading">Loading preview…</div>}
      {preview && (
        <form onSubmit={submit}>
          <div className="schedule-layout">
            <div className="schedule-media">
              {preview.media.map((media) =>
                media.kind === 'video' ? (
                  <video key={media.id} src={media.url} controls className="schedule-media-item" />
                ) : (
                  <img key={media.id} src={media.url} alt={media.name} className="schedule-media-item" />
                ),
              )}
              <span className="page-subtitle">
                {preview.post_type === 'carousel' ? `Carousel · ${preview.media.length} images` : preview.post_type}
              </span>
            </div>
            <div className="schedule-form">
              <div className="field">
                <span>Post to</span>
                {connected.length === 0 ? (
                  <div className="alert alert-warning">
                    No connected accounts.{' '}
                    <Link to={`/companies/${companyId}/social-accounts`}>Connect Instagram, Facebook or LinkedIn</Link> first.
                  </div>
                ) : (
                  <div className="account-picker">
                    {connected.map((account) => (
                      <label key={account.id} className={`account-option ${selected.includes(account.id) ? 'account-option-on' : ''}`}>
                        <input type="checkbox" checked={selected.includes(account.id)} onChange={() => toggle(account.id)} />
                        <span>
                          <strong>{account.platform_display}</strong> · {account.account_name}
                          {account.profile?.username ? ` (@${account.profile.username})` : ''}
                          {account.warnings.length > 0 && selected.includes(account.id) && (
                            <span className="account-warning">⚠ {account.warnings.join(' ')}</span>
                          )}
                        </span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
              <label className="field">
                <span>Caption</span>
                <textarea rows={6} value={caption} onChange={(e) => setCaption(e.target.value)} />
              </label>
              <div className="field">
                <span>When</span>
                <div className="segmented">
                  <button type="button" className={mode === 'schedule' ? 'active' : ''} onClick={() => setMode('schedule')}>
                    Schedule
                  </button>
                  <button type="button" className={mode === 'now' ? 'active' : ''} onClick={() => setMode('now')}>
                    Publish now
                  </button>
                </div>
                {mode === 'schedule' && (
                  <>
                    <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />
                    <span className="field-hint-inline">Your local time. Planned slot: {formatDateTime(preview.suggested_publish_at)}.</span>
                  </>
                )}
              </div>
            </div>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving || selected.length === 0}>
              {saving ? 'Saving…' : mode === 'now' ? `Publish to ${selected.length}` : `Schedule to ${selected.length}`}
            </button>
          </div>
        </form>
      )}
    </Modal>
  )
}
