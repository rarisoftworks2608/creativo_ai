import { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { cancelJob, listJobs } from '../api/jobs'
import { extractErrorMessage } from '../api/client'

const TYPES = [
  { value: '', label: 'All types' },
  { value: 'creative', label: 'Creative Generation' },
  { value: 'video', label: 'Video Generation' },
  { value: 'publishing', label: 'Publishing' },
  { value: 'report', label: 'Report Generation' },
  { value: 'analytics', label: 'Analytics Sync' },
]

const STATUSES = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'queued', label: 'Queued' },
  { value: 'processing', label: 'Processing' },
  { value: 'rendering', label: 'Rendering' },
  { value: 'succeeded', label: 'Succeeded' },
  { value: 'failed', label: 'Failed' },
]

const CANCELLABLE = ['pending', 'queued']
const CANCELLABLE_TYPES = ['creative', 'video', 'publishing']

export default function JobsPage() {
  const { isAdmin } = useAuth()

  const [jobs, setJobs] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [cancellingKey, setCancellingKey] = useState('')

  const [type, setType] = useState('')
  const [status, setStatus] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const data = await listJobs({ type, status })
      setJobs(data.results)
      setCount(data.count)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load the job queue.'))
    } finally {
      setLoading(false)
    }
  }, [type, status])

  useEffect(() => {
    if (!isAdmin) return
    const timeout = setTimeout(load, 200)
    return () => clearTimeout(timeout)
  }, [isAdmin, load])

  if (!isAdmin) return <Navigate to="/companies" replace />

  async function handleCancel(job) {
    const key = `${job.type}-${job.id}`
    setCancellingKey(key)
    try {
      await cancelJob(job.type, job.id)
      await load()
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not cancel this job.'))
    } finally {
      setCancellingKey('')
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Background Jobs</h1>
          <p className="page-subtitle">{count} background jobs - generation, publishing, reports and analytics sync</p>
        </div>
      </div>

      <div className="toolbar">
        <select className="status-select" value={type} onChange={(event) => setType(event.target.value)}>
          {TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
        <select className="status-select" value={status} onChange={(event) => setStatus(event.target.value)}>
          {STATUSES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      <div className="card">
        {loading ? (
          <div className="empty-state">Loading…</div>
        ) : jobs.length === 0 ? (
          <div className="empty-state">
            <p>No jobs found.</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="table table-stack">
              <thead>
                <tr>
                  <th>Created</th>
                  <th>Type</th>
                  <th>Company</th>
                  <th>Status</th>
                  <th>Error</th>
                  <th>Retries</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => {
                  const key = `${job.type}-${job.id}`
                  return (
                    <tr key={key}>
                      <td data-label="Created">{new Date(job.created_at).toLocaleString()}</td>
                      <td data-label="Type">
                        {job.type_display}
                        {job.detail && <div className="page-subtitle">{job.detail}</div>}
                      </td>
                      <td data-label="Company">{job.company_name}</td>
                      <td data-label="Status">
                        <span className={`badge ${job.status === 'failed' ? 'badge-inactive' : job.status === 'succeeded' ? 'badge-active' : ''}`}>
                          {job.status_display}
                        </span>
                      </td>
                      <td data-label="Error">{job.error_message ? job.error_message.slice(0, 80) : <span className="muted">—</span>}</td>
                      <td data-label="Retries">{job.retry_count}</td>
                      <td>
                        {CANCELLABLE.includes(job.status) && CANCELLABLE_TYPES.includes(job.type) && (
                          <button
                            type="button"
                            className="btn-link btn-link-danger"
                            disabled={cancellingKey === key}
                            onClick={() => handleCancel(job)}
                          >
                            {cancellingKey === key ? 'Cancelling…' : 'Cancel'}
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
