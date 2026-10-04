import { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import {
  createAdminReport,
  deleteAdminReport,
  downloadAdminReport,
  getAdminReport,
  listAdminReports,
  regenerateAdminReport,
} from '../api/reports'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import Modal from '../components/Modal'
import ReportList from '../components/ReportList'
import ReportViewer from '../components/ReportViewer'
import Tabs from '../components/Tabs'
import { rangePreset } from '../utils/format'

const TYPES = [
  { value: 'company_overview', label: 'Company report' },
  { value: 'client_overview', label: 'Client report' },
  { value: 'ai_usage', label: 'AI usage report' },
  { value: 'approval', label: 'Approval report' },
  { value: 'publishing_overview', label: 'Publishing report' },
  { value: 'subscription', label: 'Subscription report' },
]

export default function AdminReportsPage() {
  const { isAdmin } = useAuth()
  const [scope, setScope] = useState('platform')
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [form, setForm] = useState({ report_type: 'company_overview', ...rangePreset('last_month') })
  const [creating, setCreating] = useState(false)
  const [viewing, setViewing] = useState(null)

  const load = useCallback(async () => {
    setError('')
    try {
      const data = await listAdminReports({ scope })
      setReports(data.results)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load reports.'))
    } finally {
      setLoading(false)
    }
  }, [scope])

  useEffect(() => {
    if (isAdmin) load()
  }, [isAdmin, load])

  useEffect(() => {
    if (!reports.some((r) => r.status === 'pending' || r.status === 'generating')) return undefined
    const timer = setInterval(load, 4000)
    return () => clearInterval(timer)
  }, [reports, load])

  if (!isAdmin) return <Navigate to="/client" replace />

  async function create(event) {
    event.preventDefault()
    setCreating(true)
    setError('')
    try {
      await createAdminReport({ report_type: form.report_type, period_start: form.start, period_end: form.end })
      setScope('platform')
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not generate the report.'))
    } finally {
      setCreating(false)
    }
  }

  async function act(report, action) {
    setBusyId(report.id)
    try {
      if (action === 'regenerate') await regenerateAdminReport(report.id)
      if (action === 'delete') {
        if (!window.confirm('Delete this report?')) return
        await deleteAdminReport(report.id)
      }
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'That action failed.'))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Reports</h1>
          <p className="page-subtitle">
            Platform-wide admin reports. Company reports (monthly, engagement, growth…) live on each company&apos;s Reports page and
            are generated automatically every month.
          </p>
        </div>
      </div>

      <form className="card report-builder" onSubmit={create}>
        <label className="field">
          <span>Report</span>
          <select value={form.report_type} onChange={(e) => setForm((p) => ({ ...p, report_type: e.target.value }))}>
            {TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>From</span>
          <input type="date" value={form.start} onChange={(e) => setForm((p) => ({ ...p, start: e.target.value }))} required />
        </label>
        <label className="field">
          <span>To</span>
          <input type="date" value={form.end} onChange={(e) => setForm((p) => ({ ...p, end: e.target.value }))} required />
        </label>
        <button type="submit" className="btn btn-primary" disabled={creating}>
          {creating ? 'Starting…' : 'Generate'}
        </button>
      </form>

      <Tabs
        tabs={[
          { value: 'platform', label: 'Admin reports' },
          { value: 'company', label: 'All company reports' },
        ]}
        value={scope}
        onChange={setScope}
      />
      {error && <div className="alert alert-error">{error}</div>}
      {loading ? (
        <div className="page-loading">Loading…</div>
      ) : (
        <ReportList
          reports={reports}
          canManage
          busyId={busyId}
          onView={async (r) => setViewing(await getAdminReport(r.id))}
          onDownload={(r, fmt) => downloadAdminReport(r.id, fmt).catch((err) => setError(extractErrorMessage(err, 'Download failed.')))}
          onRegenerate={(r) => act(r, 'regenerate')}
          onDelete={(r) => act(r, 'delete')}
        />
      )}

      {viewing && (
        <Modal title={viewing.title || viewing.report_type_display} onClose={() => setViewing(null)} width={960}>
          <ReportViewer document={viewing.data} />
        </Modal>
      )}
    </div>
  )
}
