import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getMyCompany } from '../api/companies'
import { approveCalendarItem, listCalendarItems, rejectCalendarItem } from '../api/contentCalendar'
import { extractErrorMessage } from '../api/client'
import Modal from '../components/Modal'

export default function ClientDashboardPage() {
  const [company, setCompany] = useState(null)
  const [pendingItems, setPendingItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [busyId, setBusyId] = useState(null)

  const [rejectingItem, setRejectingItem] = useState(null)
  const [feedback, setFeedback] = useState('')
  const [rejectError, setRejectError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const companyData = await getMyCompany()
      const itemsData = await listCalendarItems(companyData.id, { status: 'pending_approval' })
      setCompany(companyData)
      setPendingItems(itemsData.results)
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

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>{company.name}</h1>
          <p className="page-subtitle">Your content dashboard</p>
        </div>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      <div className="detail-grid">
        <div className="card">
          <div className="card-header">
            <h2>Brand</h2>
          </div>
          <p className="page-subtitle">Your logo, colors, guidelines and marketing information.</p>
          <Link to={`/companies/${company.id}/brand`} className="btn btn-primary">
            View brand
          </Link>
        </div>
        <div className="card">
          <div className="card-header">
            <h2>Content calendar</h2>
          </div>
          <p className="page-subtitle">Everything planned for this month.</p>
          <Link to={`/companies/${company.id}/calendar`} className="btn btn-primary">
            View calendar
          </Link>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2>Pending your approval ({pendingItems.length})</h2>
        </div>

        {pendingItems.length === 0 ? (
          <div className="empty-state">
            <p>Nothing waiting on you right now.</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Topic</th>
                  <th>Type</th>
                  <th>Scheduled</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pendingItems.map((item) => (
                  <tr key={item.id}>
                    <td>{item.topic}</td>
                    <td>{item.content_type}</td>
                    <td>{item.scheduled_date}</td>
                    <td className="table-actions">
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
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
