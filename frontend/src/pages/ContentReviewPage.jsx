import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { approveCalendarItem, listCalendarItems, rejectCalendarItem } from '../api/contentCalendar'
import { getItemHistory } from '../api/approvals'
import { selectVariation } from '../api/creativeGeneration'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useCompanyWorkspace } from '../context/CompanyWorkspaceContext'
import ContentPreview from '../components/ContentPreview'
import Modal from '../components/Modal'
import ReviewTimeline from '../components/ReviewTimeline'
import Tabs from '../components/Tabs'
import { formatDate, formatDateTime, platformLabel } from '../utils/format'

const TABS = [
  { value: 'pending_approval', label: 'Waiting for review' },
  { value: 'generating', label: 'Being revised' },
  { value: 'approved', label: 'Approved' },
  { value: 'published', label: 'Published' },
  { value: 'rejected', label: 'Changes requested' },
]

export default function ContentReviewPage() {
  const { id: companyId } = useParams()
  const [searchParams] = useSearchParams()
  const highlightId = Number(searchParams.get('item')) || null
  const { isAdmin } = useAuth()
  const workspace = useCompanyWorkspace()

  const [tab, setTab] = useState('pending_approval')
  const [items, setItems] = useState([])
  const [counts, setCounts] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [selectingId, setSelectingId] = useState(null)

  const [approving, setApproving] = useState(null)
  const [approveNote, setApproveNote] = useState('')
  const [rejecting, setRejecting] = useState(null)
  const [feedback, setFeedback] = useState('')
  const [modalError, setModalError] = useState('')
  const [history, setHistory] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [current, ...others] = await Promise.all([
        listCalendarItems(companyId, { status: tab }),
        ...TABS.filter((t) => t.value !== tab).map((t) => listCalendarItems(companyId, { status: t.value })),
      ])
      setItems(current.results)
      const nextCounts = { [tab]: current.count }
      TABS.filter((t) => t.value !== tab).forEach((t, index) => {
        nextCounts[t.value] = others[index].count
      })
      setCounts(nextCounts)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load content for review.'))
    } finally {
      setLoading(false)
    }
  }, [companyId, tab])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!highlightId || loading) return
    const element = document.getElementById(`review-item-${highlightId}`)
    if (element) element.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [highlightId, loading, items])

  const tabs = useMemo(() => TABS.map((t) => ({ ...t, count: counts[t.value] })), [counts])

  async function handleSelectVariation(item, variationId) {
    setSelectingId(variationId)
    try {
      const updated = await selectVariation(companyId, item.latest_generation_request.id, variationId)
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, latest_generation_request: updated } : i)))
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not select this version.'))
    } finally {
      setSelectingId(null)
    }
  }

  async function handleApprove(event) {
    event.preventDefault()
    const item = approving
    setBusyId(item.id)
    setModalError('')
    try {
      const selected = item.latest_generation_request?.variations?.find((v) => v.is_selected)
      await approveCalendarItem(companyId, item.id, { variationId: selected?.id, note: approveNote.trim() })
      setApproving(null)
      setApproveNote('')
      await load()
    } catch (err) {
      setModalError(extractErrorMessage(err, 'Could not approve this content.'))
    } finally {
      setBusyId(null)
    }
  }

  async function handleReject(event) {
    event.preventDefault()
    const item = rejecting
    setBusyId(item.id)
    setModalError('')
    try {
      await rejectCalendarItem(companyId, item.id, feedback.trim())
      setRejecting(null)
      setFeedback('')
      await load()
    } catch (err) {
      setModalError(extractErrorMessage(err, 'Could not submit your feedback.'))
    } finally {
      setBusyId(null)
    }
  }

  async function openHistory(item) {
    setHistory({ item, loading: true })
    try {
      const data = await getItemHistory(companyId, item.id)
      setHistory({ item, loading: false, data })
    } catch (err) {
      setHistory({ item, loading: false, error: extractErrorMessage(err, 'Could not load the history.') })
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Content approvals</h1>
          <p className="page-subtitle">
            {workspace?.company?.name ? `${workspace.company.name} · ` : ''}
            Review generated creatives and videos, approve them for publishing, or request changes (one automatic
            regeneration per item).
          </p>
        </div>
      </div>

      <Tabs tabs={tabs} value={tab} onChange={setTab} ariaLabel="Review status" />
      {error && <div className="alert alert-error">{error}</div>}

      {loading ? (
        <div className="page-loading">Loading…</div>
      ) : items.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <p>
              {tab === 'pending_approval'
                ? 'Nothing is waiting for review right now.'
                : `No content in “${TABS.find((t) => t.value === tab)?.label}”.`}
            </p>
          </div>
        </div>
      ) : (
        <div className="request-list">
          {items.map((item) => {
            const isPending = item.status === 'pending_approval'
            return (
              <article
                key={item.id}
                id={`review-item-${item.id}`}
                className={`card review-card ${highlightId === item.id ? 'review-card-highlight' : ''}`}
              >
                <div className="card-header card-header-wrap">
                  <div>
                    <h2>{item.topic}</h2>
                    <p className="page-subtitle">
                      {item.content_type} · {formatDate(item.scheduled_date)}
                      {item.scheduled_time ? ` ${item.scheduled_time.slice(0, 5)}` : ''} ·{' '}
                      {(item.platforms || []).map(platformLabel).join(', ')}
                    </p>
                  </div>
                  <div className="card-header-actions">
                    {item.regeneration_count > 0 && <span className="badge status-badge status-scheduled">Revised</span>}
                    <span className={`badge status-badge status-${item.status}`}>{item.status_display}</span>
                  </div>
                </div>

                {item.client_feedback && (item.status === 'rejected' || item.status === 'generating') && (
                  <div className="alert alert-warning">
                    <strong>Requested changes:</strong> {item.client_feedback}
                  </div>
                )}

                <ContentPreview
                  item={item}
                  onSelectVariation={isPending ? (variationId) => handleSelectVariation(item, variationId) : undefined}
                  selectingId={selectingId}
                />

                {item.publish_jobs?.length > 0 && (
                  <div className="publish-chips">
                    {item.publish_jobs.map((job) => (
                      <span key={job.id} className={`badge status-badge pub-status-${job.status}`}>
                        {platformLabel(job.platform)}: {job.status}
                        {job.status === 'scheduled' && job.scheduled_at ? ` · ${formatDateTime(job.scheduled_at)}` : ''}
                        {job.external_url && (
                          <a href={job.external_url} target="_blank" rel="noreferrer" className="chip-link">
                            ↗
                          </a>
                        )}
                      </span>
                    ))}
                  </div>
                )}

                <div className="modal-actions card-actions">
                  <button type="button" className="btn btn-ghost" onClick={() => openHistory(item)}>
                    History
                  </button>
                  {isPending && (
                    <>
                      <button
                        type="button"
                        className="btn btn-ghost btn-danger-outline"
                        disabled={busyId === item.id}
                        onClick={() => {
                          setRejecting(item)
                          setFeedback('')
                          setModalError('')
                        }}
                      >
                        Request changes
                      </button>
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={busyId === item.id}
                        onClick={() => {
                          setApproving(item)
                          setApproveNote('')
                          setModalError('')
                        }}
                      >
                        Approve
                      </button>
                    </>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}

      {approving && (
        <Modal title={`Approve “${approving.topic}”`} onClose={() => setApproving(null)}>
          <form onSubmit={handleApprove}>
            {modalError && <div className="alert alert-error">{modalError}</div>}
            {approving.latest_generation_request?.variations?.length > 1 && (
              <p className="modal-hint">
                Approving{' '}
                <strong>
                  Variation{' '}
                  {approving.latest_generation_request.variations.find((v) => v.is_selected)?.variation_number || 1}
                </strong>
                . Close this and pick another version first if you prefer a different one.
              </p>
            )}
            <label className="field">
              <span>Note (optional)</span>
              <textarea rows={3} value={approveNote} onChange={(e) => setApproveNote(e.target.value)} placeholder="Anything the team should know" />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setApproving(null)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={busyId === approving.id}>
                {busyId === approving.id ? 'Approving…' : 'Approve'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {rejecting && (
        <Modal title={`Request changes to “${rejecting.topic}”`} onClose={() => setRejecting(null)}>
          <form onSubmit={handleReject}>
            {modalError && <div className="alert alert-error">{modalError}</div>}
            <p className="modal-hint">
              {rejecting.regeneration_count < 1
                ? 'Your feedback goes straight into one automatic AI regeneration - be specific about what to change.'
                : 'This item already used its automatic regeneration, so the team will revise it manually from your feedback.'}
            </p>
            <label className="field">
              <span>What should change? *</span>
              <textarea rows={4} value={feedback} onChange={(e) => setFeedback(e.target.value)} required autoFocus />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setRejecting(null)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={busyId === rejecting.id || !feedback.trim()}>
                {busyId === rejecting.id ? 'Sending…' : 'Send feedback'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {history && (
        <Modal title={`History · ${history.item.topic}`} onClose={() => setHistory(null)} width={760}>
          {history.loading && <div className="page-loading">Loading…</div>}
          {history.error && <div className="alert alert-error">{history.error}</div>}
          {history.data && (
            <div className="history-layout">
              <section>
                <h3 className="section-title">Activity</h3>
                <ReviewTimeline events={history.data.events} />
              </section>
              <section>
                <h3 className="section-title">Versions ({history.data.generations.length})</h3>
                {history.data.generations.length === 0 && <p className="page-subtitle">No generations yet.</p>}
                <div className="version-list">
                  {history.data.generations.map((generation, index) => (
                    <div key={`${generation.kind}-${generation.request.id}`} className="version-card">
                      <div className="version-head">
                        <strong>{index === 0 ? 'Latest' : `Version ${history.data.generations.length - index}`}</strong>
                        <span className="page-subtitle">
                          {generation.kind === 'video' ? 'Video' : 'Creative'} · {formatDateTime(generation.created_at)} ·{' '}
                          {generation.request.status}
                        </span>
                      </div>
                      {generation.kind === 'creative' ? (
                        <div className="version-thumbs">
                          {generation.request.variations.map((v) => (
                            <img key={v.id} src={v.image} alt={`Variation ${v.variation_number}`} className={v.is_selected ? 'thumb-selected' : ''} />
                          ))}
                        </div>
                      ) : generation.request.thumbnail ? (
                        <div className="version-thumbs">
                          <img src={generation.request.thumbnail} alt="Video thumbnail" />
                        </div>
                      ) : null}
                      {generation.request.prompt_brief && <p className="version-brief">{generation.request.prompt_brief}</p>}
                    </div>
                  ))}
                </div>
                {isAdmin && history.data.publish_jobs.length > 0 && (
                  <>
                    <h3 className="section-title">Publishing</h3>
                    <ul className="plain-list">
                      {history.data.publish_jobs.map((job) => (
                        <li key={job.id}>
                          {job.platform_display} · {job.status_display} · {formatDateTime(job.published_at || job.scheduled_at)}
                          {job.last_error ? ` — ${job.last_error}` : ''}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </section>
            </div>
          )}
        </Modal>
      )}
    </div>
  )
}
