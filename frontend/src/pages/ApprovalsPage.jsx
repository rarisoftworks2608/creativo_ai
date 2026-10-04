import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { getApprovalStats, listApprovalQueue } from '../api/approvals'
import { listCompanies } from '../api/companies'
import { approveCalendarItem, rejectCalendarItem } from '../api/contentCalendar'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import ContentPreview from '../components/ContentPreview'
import Modal from '../components/Modal'
import Tabs from '../components/Tabs'
import { formatDate, platformLabel, timeAgo } from '../utils/format'

const STATUS_TABS = [
  { value: 'pending_approval', label: 'Pending', statKey: 'pending_approval' },
  { value: 'generating', label: 'Generating / revising', statKey: 'generating' },
  { value: 'rejected', label: 'Changes requested', statKey: 'rejected' },
  { value: 'approved', label: 'Approved', statKey: 'approved' },
  { value: 'failed', label: 'Failed', statKey: 'failed' },
]

export default function ApprovalsPage() {
  const { isAdmin } = useAuth()
  const [status, setStatus] = useState('pending_approval')
  const [company, setCompany] = useState('')
  const [search, setSearch] = useState('')
  const [companies, setCompanies] = useState([])
  const [items, setItems] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [rejecting, setRejecting] = useState(null)
  const [feedback, setFeedback] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [queue, statsData] = await Promise.all([
        listApprovalQueue({ status, company, search }),
        getApprovalStats(),
      ])
      setItems(queue.results)
      setStats(statsData)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load the approval queue.'))
    } finally {
      setLoading(false)
    }
  }, [status, company, search])

  useEffect(() => {
    if (isAdmin) load()
  }, [isAdmin, load])

  useEffect(() => {
    if (isAdmin) listCompanies().then((data) => setCompanies(data.results)).catch(() => {})
  }, [isAdmin])

  if (!isAdmin) return <Navigate to="/client" replace />

  async function approve(item) {
    setBusyId(item.id)
    try {
      const selected = item.latest_generation_request?.variations?.find((v) => v.is_selected)
      await approveCalendarItem(item.company, item.id, { variationId: selected?.id, note: 'Approved by admin on behalf of client' })
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not approve this content.'))
    } finally {
      setBusyId(null)
    }
  }

  async function submitReject(event) {
    event.preventDefault()
    setBusyId(rejecting.id)
    try {
      await rejectCalendarItem(rejecting.company, rejecting.id, feedback.trim())
      setRejecting(null)
      setFeedback('')
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not request changes.'))
    } finally {
      setBusyId(null)
    }
  }

  const overdueHours = stats?.overdue_hours || 24
  const tabs = STATUS_TABS.map((tab) => ({ ...tab, count: stats ? stats[tab.statKey] : undefined }))

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Approvals</h1>
          <p className="page-subtitle">Every company&apos;s content in review, oldest first.</p>
        </div>
      </div>

      {stats?.overdue > 0 && (
        <div className="alert alert-warning">
          ⚠ {stats.overdue} item{stats.overdue === 1 ? '' : 's'} waiting longer than {overdueHours} hours - clients get an
          automatic reminder, or approve on their behalf below.
        </div>
      )}

      <div className="toolbar">
        <input className="search-input" placeholder="Search topic…" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="status-select" value={company} onChange={(e) => setCompany(e.target.value)}>
          <option value="">All companies</option>
          {companies.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <Tabs tabs={tabs} value={status} onChange={setStatus} ariaLabel="Approval status" />
      {error && <div className="alert alert-error">{error}</div>}

      {loading ? (
        <div className="page-loading">Loading…</div>
      ) : items.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <p>Nothing here.</p>
          </div>
        </div>
      ) : (
        <div className="request-list">
          {items.map((item) => (
            <article className="card review-card" key={item.id}>
              <div className="card-header card-header-wrap">
                <div>
                  <h2>{item.topic}</h2>
                  <p className="page-subtitle">
                    <Link to={`/companies/${item.company}/approvals?item=${item.id}`}>{item.company_name}</Link> ·{' '}
                    {item.content_type} · {formatDate(item.scheduled_date)} · {(item.platforms || []).map(platformLabel).join(', ')}
                  </p>
                </div>
                <div className="card-header-actions">
                  {item.status === 'pending_approval' && item.pending_since && (
                    <span className="page-subtitle">waiting {timeAgo(item.pending_since).replace(' ago', '')}</span>
                  )}
                  <span className={`badge status-badge status-${item.status}`}>{item.status_display}</span>
                </div>
              </div>
              {item.client_feedback && item.status !== 'approved' && (
                <div className="alert alert-warning">
                  <strong>Feedback:</strong> {item.client_feedback}
                </div>
              )}
              <ContentPreview item={item} />
              <div className="modal-actions card-actions">
                <Link to={`/companies/${item.company}/approvals?item=${item.id}`} className="btn btn-ghost">
                  Open
                </Link>
                {item.status === 'pending_approval' && (
                  <>
                    <button
                      type="button"
                      className="btn btn-ghost btn-danger-outline"
                      disabled={busyId === item.id}
                      onClick={() => {
                        setRejecting(item)
                        setFeedback('')
                      }}
                    >
                      Request changes
                    </button>
                    <button type="button" className="btn btn-primary" disabled={busyId === item.id} onClick={() => approve(item)}>
                      {busyId === item.id ? 'Approving…' : 'Approve'}
                    </button>
                  </>
                )}
                {item.status === 'approved' && (
                  <Link to={`/companies/${item.company}/publishing`} className="btn btn-primary">
                    Schedule
                  </Link>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      {rejecting && (
        <Modal title={`Request changes to “${rejecting.topic}”`} onClose={() => setRejecting(null)}>
          <form onSubmit={submitReject}>
            <p className="modal-hint">
              {rejecting.regeneration_count < 1
                ? 'This triggers the one automatic AI regeneration with your feedback.'
                : 'Automatic regeneration was already used for this item.'}
            </p>
            <label className="field">
              <span>Feedback *</span>
              <textarea rows={4} value={feedback} onChange={(e) => setFeedback(e.target.value)} required autoFocus />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setRejecting(null)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={!feedback.trim() || busyId === rejecting.id}>
                Send
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
