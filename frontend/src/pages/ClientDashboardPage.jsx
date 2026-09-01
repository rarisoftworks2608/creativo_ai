import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getMyCompany } from '../api/companies'
import { approveCalendarItem, listCalendarItems, rejectCalendarItem } from '../api/contentCalendar'
import { selectVariation } from '../api/creativeGeneration'
import { extractErrorMessage } from '../api/client'
import Modal from '../components/Modal'
import VariationGrid from '../components/VariationGrid'
import ICONS from '../components/DashboardIcons'

// Mirrors ClientProfile.Page on the backend (companies app) - only ever shows a
// card for a page the admin actually granted on the Access Control page, so the
// two stay in lockstep instead of this dashboard hardcoding its own subset.
const QUICK_LINKS = [
  {
    key: 'brand', icon: 'image', title: 'Brand',
    description: 'Your logo, colors, guidelines and marketing information.',
    path: (id) => `/companies/${id}/brand`,
  },
  {
    key: 'calendar', icon: 'calendar', title: 'Content calendar',
    description: 'Everything planned for this month.',
    path: (id) => `/companies/${id}/calendar`,
  },
  {
    key: 'ai_strategy', icon: 'sparkle', title: 'AI strategy',
    description: 'Brand context, content planning and strategy generated for you.',
    path: (id) => `/companies/${id}/ai-strategy`,
  },
  {
    key: 'creative_generation', icon: 'wand', title: 'Creative generation',
    description: 'Review the AI-generated image creatives made for your brand.',
    path: (id) => `/companies/${id}/creative-generation`,
  },
  {
    key: 'video_generation', icon: 'video', title: 'Video generation',
    description: 'Review the AI-generated videos and reels made for your brand.',
    path: (id) => `/companies/${id}/video-generation`,
  },
]

export default function ClientDashboardPage() {
  const [company, setCompany] = useState(null)
  const [pendingItems, setPendingItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [busyId, setBusyId] = useState(null)

  const [rejectingItem, setRejectingItem] = useState(null)
  const [feedback, setFeedback] = useState('')
  const [rejectError, setRejectError] = useState('')

  const [selectingVariationId, setSelectingVariationId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const companyData = await getMyCompany()
      setCompany(companyData)
      // Only fetch pending approvals if the client actually has Calendar access -
      // without it the backend 404s this call, which would otherwise take down
      // the whole dashboard load over one missing permission.
      if ((companyData.page_permissions || []).includes('calendar')) {
        const itemsData = await listCalendarItems(companyData.id, { status: 'pending_approval' })
        setPendingItems(itemsData.results)
      } else {
        setPendingItems([])
      }
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load your dashboard.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function handleApprove(item) {
    setBusyId(item.id)
    try {
      await approveCalendarItem(company.id, item.id)
      setPendingItems((prev) => prev.filter((i) => i.id !== item.id))
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not approve this content.'))
    } finally {
      setBusyId(null)
    }
  }

  async function handleSelectVariation(item, generationRequestId, variationId) {
    setSelectingVariationId(variationId)
    try {
      const updatedRequest = await selectVariation(company.id, generationRequestId, variationId)
      setPendingItems((prev) =>
        prev.map((i) => (i.id === item.id ? { ...i, latest_generation_request: updatedRequest } : i)),
      )
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not select this variation.'))
    } finally {
      setSelectingVariationId(null)
    }
  }

  function openReject(item) {
    setRejectingItem(item)
    setFeedback('')
    setRejectError('')
  }

  async function handleReject(event) {
    event.preventDefault()
    setBusyId(rejectingItem.id)
    setRejectError('')
    try {
      await rejectCalendarItem(company.id, rejectingItem.id, feedback)
      setPendingItems((prev) => prev.filter((i) => i.id !== rejectingItem.id))
      setRejectingItem(null)
    } catch (err) {
      setRejectError(extractErrorMessage(err, 'Could not submit your feedback.'))
    } finally {
      setBusyId(null)
    }
  }

  if (loading) return <div className="page-loading">Loading…</div>
  if (loadError && !company) return <div className="alert alert-error">{loadError}</div>
  if (!company) return null

  const today = new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })
  const visibleLinks = QUICK_LINKS.filter((link) => (company.page_permissions || []).includes(link.key))

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>{company.name}</h1>
          <p className="dashboard-greeting">{today} · your content dashboard</p>
        </div>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      {pendingItems.length > 0 && (
        <>
          <h2 className="dashboard-section-title">Needs your attention</h2>
          <div className="stat-grid">
            <div className="stat-tile stat-tile-warning">
              <div className="stat-tile-icon">{ICONS.clock}</div>
              <div className="stat-tile-body">
                <div className="stat-tile-value">{pendingItems.length}</div>
                <div className="stat-tile-label">Pending your approval</div>
              </div>
            </div>
          </div>
        </>
      )}

      <h2 className="dashboard-section-title">Quick links</h2>
      {visibleLinks.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <p>No pages have been enabled for your account yet - ask your account manager for access.</p>
          </div>
        </div>
      ) : (
        <div className="quick-link-grid">
          {visibleLinks.map((link) => (
            <div className="quick-link-card" key={link.key}>
              <div className="quick-link-icon">{ICONS[link.icon]}</div>
              <h2>{link.title}</h2>
              <p>{link.description}</p>
              <Link to={link.path(company.id)} className="btn btn-primary">
                View {link.title.toLowerCase()}
              </Link>
            </div>
          ))}
        </div>
      )}

      <div className="card" style={{ marginTop: 28 }}>
        <div className="card-header">
          <h2>Pending your approval ({pendingItems.length})</h2>
        </div>

        {pendingItems.length === 0 ? (
          <div className="empty-state">
            <p>Nothing waiting on you right now.</p>
          </div>
        ) : (
          <div className="request-list">
            {pendingItems.map((item) => {
              const generationRequest = item.latest_generation_request
              const videoRequest = item.latest_video_request
              const hasVariations = generationRequest?.status === 'succeeded' && generationRequest.variations.length > 0
              const hasVideo = videoRequest?.status === 'succeeded' && videoRequest.video_file

              return (
                <div className="card request-card" key={item.id}>
                  <div className="card-header">
                    <div>
                      <h2>{item.topic}</h2>
                      <p className="page-subtitle">
                        {item.content_type} · {item.scheduled_date}
                      </p>
                    </div>
                  </div>

                  {hasVariations && (
                    <>
                      <p className="modal-hint">Pick your favorite version, then Approve.</p>
                      <VariationGrid
                        variations={generationRequest.variations}
                        selecting={selectingVariationId}
                        onSelect={(variationId) => handleSelectVariation(item, generationRequest.id, variationId)}
                      />
                    </>
                  )}

                  {hasVideo && (
                    <video controls src={videoRequest.video_file} poster={videoRequest.thumbnail || undefined} className="variation-image" />
                  )}

                  {!hasVariations && !hasVideo && <p className="page-subtitle">Preview not available for this item.</p>}

                  <div className="modal-actions">
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={busyId === item.id}
                      onClick={() => handleApprove(item)}
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      className="btn-link btn-link-danger"
                      disabled={busyId === item.id}
                      onClick={() => openReject(item)}
                    >
                      Reject
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {rejectingItem && (
        <Modal title={`Reject "${rejectingItem.topic}"`} onClose={() => setRejectingItem(null)}>
          <form onSubmit={handleReject}>
            {rejectError && <div className="alert alert-error">{rejectError}</div>}
            <p className="modal-hint">
              Tell us what to change — this feeds directly into one automatic regeneration.
            </p>
            <label className="field">
              <span>Feedback *</span>
              <textarea rows={4} value={feedback} onChange={(e) => setFeedback(e.target.value)} required autoFocus />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setRejectingItem(null)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={busyId === rejectingItem.id}>
                {busyId === rejectingItem.id ? 'Submitting…' : 'Submit feedback & reject'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
