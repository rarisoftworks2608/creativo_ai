import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { createVideoRequest, listVideoRequests, retryVideoRequest } from '../api/videoGeneration'
import { generateNowCalendarItem, listCalendarItems } from '../api/contentCalendar'
import { getCompany } from '../api/companies'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import Modal from '../components/Modal'
import ContentQueue from '../components/ContentQueue'
import { isVideoContentType } from '../utils/contentType'

const VIDEO_TYPES = [
  { value: 'instagram_reel', label: 'Instagram Reel' },
  { value: 'facebook_reel', label: 'Facebook Reel' },
  { value: 'linkedin_video', label: 'LinkedIn Video' },
  { value: 'short_video', label: 'Short Video' },
  { value: 'promotional_video', label: 'Promotional Video' },
  { value: 'product_video', label: 'Product Video' },
  { value: 'educational_video', label: 'Educational Video' },
]

const ASPECT_RATIOS = [
  { value: '9:16', label: 'Vertical (9:16) - Reels/Stories' },
  { value: '1:1', label: 'Square (1:1)' },
  { value: '16:9', label: 'Landscape (16:9)' },
]

const IN_PROGRESS_STATUSES = ['pending', 'queued', 'processing', 'rendering']

const EMPTY_FORM = {
  video_type: 'instagram_reel',
  content_calendar_item: '',
  aspect_ratio: '9:16',
  target_duration_seconds: 30,
  prompt_brief: '',
  product_info: '',
  voice_over_enabled: true,
  subtitles_enabled: true,
  include_logo: true,
  ai_motion_enabled: true,
}

export default function VideoGenerationPage() {
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
    setLoading(true)
    setLoadError('')
    try {
      // Calendar item linkage and the queue are admin-only concerns (Access
      // Control page's Calendar permission is separate from Video Generation) -
      // skip that fetch for a client so a missing Calendar grant can't take down
      // a page they otherwise do have access to.
      const [companyData, requestsData, calendarData] = await Promise.all([
        getCompany(companyId),
        listVideoRequests(companyId),
        isAdmin ? listCalendarItems(companyId) : Promise.resolve({ results: [] }),
      ])
      setCompany(companyData)
      setRequests(requestsData.results)
      setCalendarItems(calendarData.results)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load video generation requests.'))
    } finally {
      setLoading(false)
    }
  }, [companyId, isAdmin])

  useEffect(() => {
    load()
  }, [load])

  const refreshList = useCallback(async () => {
    try {
      const data = await listVideoRequests(companyId)
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
      pollRef.current = setInterval(refreshList, 3000)
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [requests, refreshList])

  function updateForm(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleCreate(event) {
    event.preventDefault()
    setCreating(true)
    setCreateError('')
    try {
      const payload = { ...form, content_calendar_item: form.content_calendar_item || null }
      const created = await createVideoRequest(companyId, payload)
      setRequests((prev) => [created, ...prev])
      setShowCreate(false)
      setForm(EMPTY_FORM)
    } catch (err) {
      setCreateError(extractErrorMessage(err, 'Could not start this video generation.'))
    } finally {
      setCreating(false)
    }
  }

  async function handleRetry(requestId) {
    try {
      const updated = await retryVideoRequest(companyId, requestId)
      setRequests((prev) => prev.map((r) => (r.id === updated.id ? updated : r)))
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not retry this generation.'))
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
          <h1>AI Video Generation</h1>
          <p className="page-subtitle">{company.name}</p>
        </div>
        {isAdmin && (
          <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
            + New video
          </button>
        )}
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      {isAdmin && (
        <ContentQueue
          items={calendarItems.filter((item) => isVideoContentType(item.content_type))}
          onGenerateNow={handleGenerateNow}
          generatingId={generatingItemId}
          emptyMessage="Nothing waiting in the calendar - planned reels/videos will appear here until they're generated."
        />
      )}

      {requests.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <p>No videos generated yet.</p>
          </div>
        </div>
      ) : (
        <div className="request-list">
          {requests.map((request) => (
            <VideoRequestCard key={request.id} request={request} canRetry={isAdmin} onRetry={() => handleRetry(request.id)} />
          ))}
        </div>
      )}

      {isAdmin && showCreate && (
        <Modal title="New video generation" onClose={() => setShowCreate(false)} width={640}>
          <form onSubmit={handleCreate}>
            {createError && <div className="alert alert-error">{createError}</div>}

            <div className="field-row">
              <label className="field">
                <span>Video type *</span>
                <select value={form.video_type} onChange={(e) => updateForm('video_type', e.target.value)} required>
                  {VIDEO_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Aspect ratio</span>
                <select value={form.aspect_ratio} onChange={(e) => updateForm('aspect_ratio', e.target.value)}>
                  {ASPECT_RATIOS.map((r) => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="field-row">
              <label className="field">
                <span>Target duration (seconds)</span>
                <input
                  type="number"
                  min={5}
                  max={180}
                  value={form.target_duration_seconds}
                  onChange={(e) => updateForm('target_duration_seconds', Number(e.target.value))}
                />
              </label>
              <label className="field">
                <span>Content calendar item</span>
                <select
                  value={form.content_calendar_item}
                  onChange={(e) => updateForm('content_calendar_item', e.target.value)}
                >
                  <option value="">None (auto-added to the calendar for approval)</option>
                  {calendarItems.map((item) => (
                    <option key={item.id} value={item.id}>{item.topic} ({item.scheduled_date})</option>
                  ))}
                </select>
              </label>
            </div>

            <label className="field">
              <span>Brief</span>
              <textarea
                rows={3}
                value={form.prompt_brief}
                onChange={(e) => updateForm('prompt_brief', e.target.value)}
                placeholder="What should this video be about?"
              />
            </label>
            <label className="field">
              <span>Product information</span>
              <textarea
                rows={2}
                value={form.product_info}
                onChange={(e) => updateForm('product_info', e.target.value)}
                placeholder="Defaults to the company's product list"
              />
            </label>

            <div className="checkbox-row">
              <label className="field-checkbox field-checkbox-inline">
                <input
                  type="checkbox"
                  checked={form.voice_over_enabled}
                  onChange={(e) => updateForm('voice_over_enabled', e.target.checked)}
                />
                <span>Voice-over</span>
              </label>
              <label className="field-checkbox field-checkbox-inline">
                <input
                  type="checkbox"
                  checked={form.subtitles_enabled}
                  onChange={(e) => updateForm('subtitles_enabled', e.target.checked)}
                />
                <span>Subtitles</span>
              </label>
              <label className="field-checkbox field-checkbox-inline">
                <input
                  type="checkbox"
                  checked={form.include_logo}
                  onChange={(e) => updateForm('include_logo', e.target.checked)}
                />
                <span>Include logo</span>
              </label>
              <label className="field-checkbox field-checkbox-inline">
                <input
                  type="checkbox"
                  checked={form.ai_motion_enabled}
                  onChange={(e) => updateForm('ai_motion_enabled', e.target.checked)}
                />
                <span>AI motion (animate scenes)</span>
              </label>
            </div>

            <p className="modal-hint">
              Generates a script and scene breakdown, an AI visual and voice-over per scene, then renders one
              final video. This runs in the background and can take a few minutes.
            </p>

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
  rendering: 'Rendering',
  succeeded: 'Succeeded',
  failed: 'Failed',
}

const IN_PROGRESS_MESSAGES = {
  pending: 'Getting started…',
  queued: 'Queued…',
  processing: 'Writing the script and generating scene visuals + voice-over…',
  rendering: 'Rendering the final video with FFmpeg…',
}

function VideoRequestCard({ request, canRetry, onRetry }) {
  const typeLabel = VIDEO_TYPES.find((t) => t.value === request.video_type)?.label || request.video_type
  const inProgress = IN_PROGRESS_STATUSES.includes(request.status)

  return (
    <div className="card request-card">
      <div className="card-header">
        <div>
          <h2>{typeLabel}</h2>
          <p className="page-subtitle">
            {new Date(request.created_at).toLocaleString()}
            {request.retry_count > 0 ? ` · retried ${request.retry_count}×` : ''}
            {request.duration_seconds ? ` · ${Math.round(request.duration_seconds)}s · ${request.resolution}` : ''}
          </p>
        </div>
        <span className={`badge status-badge gen-status-${request.status}`}>{STATUS_LABELS[request.status]}</span>
      </div>

      {request.prompt_brief && <p className="modal-hint">{request.prompt_brief}</p>}

      {inProgress && (
        <div className="empty-state">
          <p>{IN_PROGRESS_MESSAGES[request.status] || 'Working…'}</p>
        </div>
      )}

      {request.status === 'failed' && (
        <>
          <div className="alert alert-error">{request.error_message}</div>
          {canRetry && (
            <button type="button" className="btn btn-ghost" onClick={onRetry}>
              Retry
            </button>
          )}
        </>
      )}

      {request.status === 'succeeded' && (
        <div className="video-result">
          <video className="video-preview" src={request.video_file} poster={request.thumbnail} controls />
          <div className="scene-grid">
            {request.scenes.map((scene) => (
              <div className="scene-card" key={scene.id}>
                {scene.image && <img src={scene.image} alt={`Scene ${scene.scene_number}`} className="scene-image" />}
                <div className="scene-body">
                  <div className="scene-label">Scene {scene.scene_number}</div>
                  <p className="scene-narration">{scene.narration}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
