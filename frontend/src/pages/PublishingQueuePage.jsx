import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { listGlobalPublishQueue } from '../api/publishing'
import { listCompanies } from '../api/companies'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { formatDateTime } from '../utils/format'

const STATUS_OPTIONS = [
  { value: 'scheduled,queued,processing', label: 'Upcoming' },
  { value: 'published', label: 'Published' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: '', label: 'All' },
]

export default function PublishingQueuePage() {
  const { isAdmin } = useAuth()
  const [status, setStatus] = useState('scheduled,queued,processing')
  const [platform, setPlatform] = useState('')
  const [company, setCompany] = useState('')
  const [companies, setCompanies] = useState([])
  const [jobs, setJobs] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = {}
      if (status) params.status = status
      if (platform) params.platform = platform
      if (company) params.company = company
      if (status.startsWith('scheduled')) params.upcoming = 'true'
      const data = await listGlobalPublishQueue(params)
      setJobs(data.results)
      setCount(data.count)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load the publishing queue.'))
    } finally {
      setLoading(false)
    }
  }, [status, platform, company])

  useEffect(() => {
    if (isAdmin) load()
  }, [isAdmin, load])

  useEffect(() => {
    if (isAdmin) listCompanies().then((data) => setCompanies(data.results)).catch(() => {})
  }, [isAdmin])

  if (!isAdmin) return <Navigate to="/client" replace />

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Publishing queue</h1>
          <p className="page-subtitle">Every company&apos;s scheduled, published and failed posts ({count}).</p>
        </div>
      </div>

      <div className="toolbar">
        <select className="status-select" value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUS_OPTIONS.map((o) => (
            <option key={o.label} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select className="status-select" value={platform} onChange={(e) => setPlatform(e.target.value)}>
          <option value="">All platforms</option>
          <option value="instagram">Instagram</option>
          <option value="facebook">Facebook</option>
          <option value="linkedin">LinkedIn</option>
        </select>
        <select className="status-select" value={company} onChange={(e) => setCompany(e.target.value)}>
          <option value="">All companies</option>
          {companies.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {loading ? (
        <div className="page-loading">Loading…</div>
      ) : jobs.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <p>No posts match these filters.</p>
          </div>
        </div>
      ) : (
        <div className="card card-flush">
          <div className="table-wrapper">
            <table className="table table-stack">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Company</th>
                  <th>Content</th>
                  <th>Platform</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td data-label="When">{formatDateTime(job.published_at || job.scheduled_at)}</td>
                    <td data-label="Company">
                      <Link to={`/companies/${job.company}/publishing`}>{job.company_name}</Link>
                    </td>
                    <td data-label="Content">
                      {job.topic || `Post #${job.id}`}
                      {job.last_error && job.status !== 'published' && <div className="cell-error">{job.last_error}</div>}
                    </td>
                    <td data-label="Platform">
                      {job.platform_display} · {job.account_name}
                    </td>
                    <td data-label="Status">
                      <span className={`badge status-badge pub-status-${job.status}`}>{job.status_display}</span>
                    </td>
                    <td className="table-actions">
                      {job.external_url && (
                        <a href={job.external_url} target="_blank" rel="noreferrer" className="btn-link">
                          View ↗
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
