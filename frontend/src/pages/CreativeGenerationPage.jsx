import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  createGenerationRequest,
  listGenerationRequests,
  retryGenerationRequest,
  selectVariation,
} from '../api/creativeGeneration'
import { generateNowCalendarItem, listCalendarItems } from '../api/contentCalendar'
import { getCompany } from '../api/companies'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import Modal from '../components/Modal'
import VariationGrid from '../components/VariationGrid'
import ContentQueue from '../components/ContentQueue'
import { isVideoContentType } from '../utils/contentType'

const CREATIVE_TYPES = [
  { value: 'instagram_post', label: 'Instagram Post' },
  { value: 'facebook_post', label: 'Facebook Post' },
  { value: 'linkedin_post', label: 'LinkedIn Post' },
  { value: 'carousel', label: 'Carousel' },
  { value: 'story', label: 'Story' },
  { value: 'promotional_creative', label: 'Promotional Creative' },
  { value: 'festival_creative', label: 'Festival Creative' },
  { value: 'product_creative', label: 'Product Creative' },
]

const IN_PROGRESS_STATUSES = ['pending', 'queued', 'processing']

const EMPTY_FORM = { creative_type: 'instagram_post', content_calendar_item: '', prompt_brief: '', product_info: '' }

export default function CreativeGenerationPage() {
  const { id: companyId } = useParams()
  const { isAdmin } = useAuth()

  const [company, setCompany] = useState(null)
  const [requests, setRequests] = useState([])
  const [calendarItems, setCalendarItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  const [generatingItemId, setGeneratingItemId] = useState(null)

  const pollRef = useRef(null)

  const load = useCallback(async () => {
    if (!isAdmin) {
      setLoading(false)
      return
    }
    setLoading(true)
    setLoadError('')
    try {
      const [companyData, requestsData, calendarData] = await Promise.all([
        getCompany(companyId),
        listGenerationRequests(companyId),
        listCalendarItems(companyId),
      ])
      setCompany(companyData)
      setRequests(requestsData.results)
      setCalendarItems(calendarData.results)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load creative generation requests.'))
    } finally {
      setLoading(false)
    }
  }, [companyId, isAdmin])

  useEffect(() => {
    load()
  }, [load])

  const refreshList = useCallback(async () => {
    try {
      const data = await listGenerationRequests(companyId)
      setRequests(data.results)
    } catch {
      // A poll failing silently is fine - the next tick tries again.
    }
  }, [companyId])

  useEffect(() => {
    const hasInProgress = requests.some((r) => IN_PROGRESS_STATUSES.includes(r.status))
    if (!hasInProgress) {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
      return
    }
    if (!pollRef.current) {
      pollRef.current = setInterval(refreshList, 2500)
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [requests, refreshList])

  async function handleCreate(event) {
    event.preventDefault()
    setCreating(true)
    setCreateError('')
    try {
      const payload = { ...form, content_calendar_item: form.content_calendar_item || null }
      const created = await createGenerationRequest(companyId, payload)
      setRequests((prev) => [created, ...prev])
      setShowCreate(false)
      setForm(EMPTY_FORM)
    } catch (err) {
      setCreateError(extractErrorMessage(err, 'Could not start this generation.'))
    } finally {
      setCreating(false)
    }
  }

  async function handleRetry(requestId) {
    try {
      const updated = await retryGenerationRequest(companyId, requestId)
      setRequests((prev) => prev.map((r) => (r.id === updated.id ? updated : r)))
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not retry this generation.'))
    }
  }

  async function handleSelectVariation(requestId, variationId) {
    try {
      const updated = await selectVariation(companyId, requestId, variationId)
      setRequests((prev) => prev.map((r) => (r.id === updated.id ? updated : r)))
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not select this variation.'))
    }
  }

  async function handleGenerateNow(itemId) {
    setGeneratingItemId(itemId)
    try {
      await generateNowCalendarItem(companyId, itemId)
      await load()
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not start generation for this item.'))
    } finally {
      setGeneratingItemId(null)
    }
  }

  if (!isAdmin) {
    return <div className="alert alert-error">AI Creative Generation is only available to admins.</div>
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
          <h1>AI Creative Generation</h1>
          <p className="page-subtitle">{company.name}</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
          + New generation
        </button>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      <ContentQueue
        items={calendarItems.filter((item) => !isVideoContentType(item.content_type))}
        onGenerateNow={handleGenerateNow}
        generatingId={generatingItemId}
        emptyMessage="Nothing waiting in the calendar - planned image/carousel/story content will appear here until it's generated."
      />

      {requests.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <p>No creative generations yet.</p>
          </div>
        </div>
      ) : (
        <div className="request-list">
          {requests.map((request) => (
            <RequestCard
              key={request.id}
              request={request}
              onRetry={() => handleRetry(request.id)}
              onSelectVariation={(variationId) => handleSelectVariation(request.id, variationId)}
            />
          ))}
        </div>
      )}

      {showCreate && (
        <Modal title="New creative generation" onClose={() => setShowCreate(false)}>
          <form onSubmit={handleCreate}>
            {createError && <div className="alert alert-error">{createError}</div>}
            <label className="field">
              <span>Creative type *</span>
              <select
                value={form.creative_type}
                onChange={(e) => setForm((p) => ({ ...p, creative_type: e.target.value }))}
                required
              >
                {CREATIVE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Content calendar item</span>
              <select
                value={form.content_calendar_item}
                onChange={(e) => setForm((p) => ({ ...p, content_calendar_item: e.target.value }))}
              >
                <option value="">None (auto-added to the calendar for approval)</option>
                {calendarItems.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.topic} ({item.scheduled_date})
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Creative brief</span>
              <textarea
                rows={3}
                value={form.prompt_brief}
                onChange={(e) => setForm((p) => ({ ...p, prompt_brief: e.target.value }))}
                placeholder="Visual direction / instructions"
              />
            </label>
            <label className="field">
              <span>Product information</span>
              <textarea
                rows={2}
                value={form.product_info}
                onChange={(e) => setForm((p) => ({ ...p, product_info: e.target.value }))}
                placeholder="Defaults to the company's product list"
              />
            </label>
            <p className="modal-hint">Generates 3 brand-aware variations (image + copy). This runs in the background.</p>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={creating}>
                {creating ? 'Starting…' : 'Generate'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}

const STATUS_LABELS = {
  pending: 'Pending',
  queued: 'Queued',
  processing: 'Processing',
  succeeded: 'Succeeded',
  failed: 'Failed',
}

function RequestCard({ request, onRetry, onSelectVariation }) {
  const typeLabel = CREATIVE_TYPES.find((t) => t.value === request.creative_type)?.label || request.creative_type
  const inProgress = IN_PROGRESS_STATUSES.includes(request.status)

  return (
    <div className="card request-card">
      <div className="card-header">
        <div>
          <h2>{typeLabel}</h2>
          <p className="page-subtitle">
            {new Date(request.created_at).toLocaleString()}
            {request.retry_count > 0 ? ` · retried ${request.retry_count}×` : ''}
          </p>
        </div>
        <span className={`badge status-badge gen-status-${request.status}`}>{STATUS_LABELS[request.status]}</span>
      </div>

      {request.prompt_brief && <p className="modal-hint">{request.prompt_brief}</p>}

      {inProgress && (
        <div className="empty-state">
          <p>Generating 3 variations… this can take a moment.</p>
        </div>
      )}

      {request.status === 'failed' && (
        <>
          <div className="alert alert-error">{request.error_message}</div>
          <button type="button" className="btn btn-ghost" onClick={onRetry}>
            Retry
          </button>
        </>
      )}

      {request.status === 'succeeded' && (
        <VariationGrid variations={request.variations} onSelect={onSelectVariation} />
      )}
    </div>
  )
}
