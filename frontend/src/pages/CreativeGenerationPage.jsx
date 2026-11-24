import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  createCreative,
  downloadCreativeZip,
  editVariation,
  getCreativeOptions,
  listGenerationRequests,
  regenerateVariation,
  retryGenerationRequest,
  selectVariation,
} from '../api/creativeGeneration'
import { generateNowCalendarItem, listCalendarItems } from '../api/contentCalendar'
import { getCompany } from '../api/companies'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import Modal from '../components/Modal'
import ContentQueue from '../components/ContentQueue'
import CreativeForm from '../components/CreativeForm'
import CreativeResult from '../components/CreativeResult'
import { isVideoContentType } from '../utils/contentType'

const IN_PROGRESS_STATUSES = ['pending', 'queued', 'processing']

function isBusy(request) {
  return IN_PROGRESS_STATUSES.includes(request.status) || request.variations.some((v) => v.status === 'processing')
}

export default function CreativeGenerationPage() {
  const { id: companyId } = useParams()
  const { isAdmin } = useAuth()

  const [company, setCompany] = useState(null)
  const [requests, setRequests] = useState([])
  const [calendarItems, setCalendarItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [options, setOptions] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  const [generatingItemId, setGeneratingItemId] = useState(null)

  const pollRef = useRef(null)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      // Calendar item linkage and the queue are admin-only concerns (Access
      // Control page's Calendar permission is separate from Creative Generation) -
      // skip that fetch for a client so a missing Calendar grant can't take down
      // a page they otherwise do have access to.
      const [companyData, requestsData, calendarData, optionsData] = await Promise.all([
        getCompany(companyId),
        listGenerationRequests(companyId),
        isAdmin ? listCalendarItems(companyId) : Promise.resolve({ results: [] }),
        getCreativeOptions(companyId).catch(() => null),
      ])
      setCompany(companyData)
      setOptions(optionsData)
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
    const hasInProgress = requests.some(isBusy)
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

  function replaceRequest(updated) {
    setRequests((prev) => prev.map((r) => (r.id === updated.id ? updated : r)))
  }

  async function handleCreate(payload, photoFile) {
    setCreating(true)
    setCreateError('')
    try {
      const created = await createCreative(companyId, payload, photoFile)
      setRequests((prev) => [created, ...prev])
      setShowCreate(false)
    } catch (err) {
      setCreateError(extractErrorMessage(err, 'Could not start this generation.'))
    } finally {
      setCreating(false)
    }
  }

  async function handleEdit(requestId, variation, payload) {
    // Errors surface inside the edit dialog, so it stays open with the message.
    const updated = await editVariation(companyId, requestId, variation.id, payload)
    replaceRequest(updated)
  }

  async function handleRegenerate(requestId, variation) {
    try {
      const updated = await regenerateVariation(companyId, requestId, variation.id)
      replaceRequest(updated)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not regenerate this image.'))
    }
  }

  async function handleDownload(requestId) {
    try {
      await downloadCreativeZip(companyId, requestId)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not download this creative.'))
    }
  }

  async function handleRetry(requestId) {
    try {
      const updated = await retryGenerationRequest(companyId, requestId)
      replaceRequest(updated)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not retry this generation.'))
    }
  }

  async function handleSelectVariation(requestId, variationId) {
    try {
      const updated = await selectVariation(companyId, requestId, variationId)
      replaceRequest(updated)
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
          <h1>Image creatives</h1>
          <p className="page-subtitle">Generate image posts for the planned content, then send them for review.</p>
        </div>
        {isAdmin && (
          <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)} disabled={!options}>
            + New creative
          </button>
        )}
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      {isAdmin && (
        <ContentQueue
          items={calendarItems.filter((item) => !isVideoContentType(item.content_type))}
          onGenerateNow={handleGenerateNow}
          generatingId={generatingItemId}
          emptyMessage="Nothing waiting in the calendar - planned image/carousel/story content will appear here until it's generated."
        />
      )}

      {requests.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <p>No creative generations yet.</p>
          </div>
        </div>
      ) : (
        <div className="request-list">
          {requests.map((request) => (
            <CreativeResult
              key={request.id}
              request={request}
              options={options}
              canManage={isAdmin}
              onRetry={() => handleRetry(request.id)}
              onSelect={(variationId) => handleSelectVariation(request.id, variationId)}
              onEdit={(variation, payload) => handleEdit(request.id, variation, payload)}
              onRegenerate={(variation) => handleRegenerate(request.id, variation)}
              onDownload={() => handleDownload(request.id)}
            />
          ))}
        </div>
      )}

      {isAdmin && showCreate && options && (
        <Modal title="New creative" onClose={() => setShowCreate(false)} width={1040}>
          <CreativeForm
            options={options}
            calendarItems={calendarItems}
            onSubmit={handleCreate}
            onCancel={() => setShowCreate(false)}
            submitting={creating}
            error={createError}
          />
        </Modal>
      )}
    </div>
  )
}
