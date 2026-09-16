import { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { listActivityLog } from '../api/activityLog'
import { extractErrorMessage } from '../api/client'

const MODULES = [
  { value: '', label: 'All modules' },
  { value: 'auth', label: 'Authentication' },
  { value: 'company', label: 'Company' },
  { value: 'client', label: 'Client' },
  { value: 'calendar', label: 'Content Calendar' },
  { value: 'creative', label: 'Creative Generation' },
  { value: 'video', label: 'Video Generation' },
  { value: 'approval', label: 'Content Approval' },
  { value: 'social', label: 'Social Accounts' },
  { value: 'settings', label: 'Settings' },
]

export default function ActivityLogPage() {
  const { isAdmin } = useAuth()

  const [entries, setEntries] = useState([])
  const [count, setCount] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [loadError, setLoadError] = useState('')

  const [search, setSearch] = useState('')
  const [module, setModule] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    setPage(1)
    try {
      const data = await listActivityLog({ search, module })
      setEntries(data.results)
      setCount(data.count)
      setHasMore(Boolean(data.next))
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load the activity log.'))
    } finally {
      setLoading(false)
    }
  }, [search, module])

  useEffect(() => {
    if (!isAdmin) return
    const timeout = setTimeout(load, 300)
    return () => clearTimeout(timeout)
  }, [isAdmin, load])

  if (!isAdmin) return <Navigate to="/companies" replace />

  async function handleLoadMore() {
    setLoadingMore(true)
    try {
      const nextPage = page + 1
      const data = await listActivityLog({ search, module, page: nextPage })
      setEntries((prev) => [...prev, ...data.results])
      setHasMore(Boolean(data.next))
      setPage(nextPage)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load more entries.'))
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Activity Log</h1>
          <p className="page-subtitle">{count} recorded actions</p>
        </div>
      </div>

      <div className="toolbar">
        <input
          type="search"
          placeholder="Search by action or description…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="search-input"
        />
        <select className="status-select" value={module} onChange={(event) => setModule(event.target.value)}>
          {MODULES.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      <div className="card">
        {loading ? (
          <div className="empty-state">Loading…</div>
        ) : entries.length === 0 ? (
          <div className="empty-state">
            <p>No activity recorded yet.</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>User</th>
                  <th>Module</th>
                  <th>Action</th>
                  <th>Description</th>
                  <th>Company</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td>{new Date(entry.created_at).toLocaleString()}</td>
                    <td>{entry.user_name}</td>
                    <td>{entry.module_display}</td>
                    <td>{entry.action}</td>
                    <td>{entry.description || <span className="muted">—</span>}</td>
                    <td>{entry.company_name || <span className="muted">—</span>}</td>
                    <td>{entry.ip_address || <span className="muted">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {hasMore && (
          <button type="button" className="btn btn-ghost" disabled={loadingMore} onClick={handleLoadMore} style={{ marginTop: 12 }}>
            {loadingMore ? 'Loading…' : 'Load more'}
          </button>
        )}
      </div>
    </div>
  )
}
