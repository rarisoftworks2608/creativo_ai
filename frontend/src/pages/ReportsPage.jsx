import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  createCompanyReport,
  deleteCompanyReport,
  downloadCompanyReport,
  getCompanyReport,
  listCompanyReports,
  regenerateCompanyReport,
  sendCompanyReport,
} from '../api/reports'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useCompanyWorkspace } from '../context/CompanyWorkspaceContext'
import Modal from '../components/Modal'
import ReportList from '../components/ReportList'
import ReportViewer from '../components/ReportViewer'
import { rangePreset } from '../utils/format'

const TYPES = [
  { value: 'monthly', label: 'Monthly report', hint: 'Everything in one: performance, top posts, growth, publishing and content.' },
  { value: 'engagement', label: 'Engagement report', hint: 'Reach, engagement, platforms, content types, campaigns.' },
  { value: 'growth', label: 'Growth report', hint: 'Follower growth per account and period-over-period change.' },
  { value: 'publishing', label: 'Publishing report', hint: 'What was published where, plus failures.' },
  { value: 'content', label: 'Content report', hint: 'Content pipeline, approvals, rejections and regenerations.' },
]
const PERIODS = [
  { value: 'last_month', label: 'Last month' },
  { value: 'month', label: 'This month so far' },
  { value: '30d', label: 'Last 30 days' },
  { value: '90d', label: 'Last 90 days' },
  { value: 'custom', label: 'Custom range' },
]

export default function ReportsPage() {
  const { id: companyId } = useParams()
  const { isAdmin } = useAuth()
  const workspace = useCompanyWorkspace()

  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ report_type: 'monthly', period: 'last_month', ...rangePreset('last_month') })
  const [creating, setCreating] = useState(false)
  const [viewing, setViewing] = useState(null)

  const load = useCallback(async () => {
    setError('')
    try {
      const data = await listCompanyReports(companyId)
      setReports(data.results)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load reports.'))
    } finally {
      setLoading(false)
    }
  }, [companyId])

  useEffect(() => {
    load()
  }, [load])

  // Poll while anything is still generating.
  useEffect(() => {
    if (!reports.some((r) => r.status === 'pending' || r.status === 'generating')) return undefined
    const timer = setInterval(load, 4000)
    return () => clearInterval(timer)
  }, [reports, load])

  function setPeriod(period) {
    setForm((prev) => ({ ...prev, period, ...(period !== 'custom' ? rangePreset(period) : {}) }))
  }

  async function create(event) {
    event.preventDefault()
    setCreating(true)
    setError('')
    try {
      await createCompanyReport(companyId, { report_type: form.report_type, period_start: form.start, period_end: form.end })
      setShowCreate(false)
      setNotice('Report is being generated - it appears below in a few seconds.')
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not generate the report.'))
    } finally {
      setCreating(false)
    }
  }

  async function act(report, action) {
    setBusyId(report.id)
    setError('')
    setNotice('')
    try {
      if (action === 'send') {
        const result = await sendCompanyReport(companyId, report.id)
        setNotice(result.detail)
      } else if (action === 'regenerate') {
        await regenerateCompanyReport(companyId, report.id)
      } else if (action === 'delete') {
        if (!window.confirm('Delete this report and its files?')) return
        await deleteCompanyReport(companyId, report.id)
      }
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'That action failed.'))
    } finally {
      setBusyId(null)
    }
  }

  async function view(report) {
    try {
      setViewing(await getCompanyReport(companyId, report.id))
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not open the report.'))
    }
  }

  async function download(report, fmt) {
    try {
      await downloadCompanyReport(companyId, report.id, fmt)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not download the report.'))
    }
  }

  const selectedType = TYPES.find((t) => t.value === form.report_type)

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Reports</h1>
          <p className="page-subtitle">
            {workspace?.company?.name ? `${workspace.company.name} · ` : ''}Monthly, engagement, growth, publishing and content reports -
            download as PDF, Excel or CSV.
          </p>
        </div>
        {isAdmin && (
          <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
            + Generate report
          </button>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      {loading ? (
        <div className="page-loading">Loading…</div>
      ) : (
        <ReportList
          reports={reports}
          canManage={isAdmin}
          busyId={busyId}
          onView={view}
          onDownload={download}
          onSend={(r) => act(r, 'send')}
          onRegenerate={(r) => act(r, 'regenerate')}
          onDelete={(r) => act(r, 'delete')}
        />
      )}

      {showCreate && (
        <Modal title="Generate report" onClose={() => setShowCreate(false)}>
          <form onSubmit={create}>
            <label className="field">
              <span>Report</span>
              <select value={form.report_type} onChange={(e) => setForm((prev) => ({ ...prev, report_type: e.target.value }))}>
                {TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
              <span className="field-hint-inline">{selectedType?.hint}</span>
            </label>
            <label className="field">
              <span>Period</span>
              <select value={form.period} onChange={(e) => setPeriod(e.target.value)}>
                {PERIODS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="field-row">
              <label className="field">
                <span>From</span>
                <input type="date" value={form.start} onChange={(e) => setForm((prev) => ({ ...prev, period: 'custom', start: e.target.value }))} required />
              </label>
              <label className="field">
                <span>To</span>
                <input type="date" value={form.end} onChange={(e) => setForm((prev) => ({ ...prev, period: 'custom', end: e.target.value }))} required />
              </label>
            </div>
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

      {viewing && (
        <Modal title={viewing.title || viewing.report_type_display} onClose={() => setViewing(null)} width={900}>
          <ReportViewer document={viewing.data} />
          <div className="modal-actions">
            {viewing.formats.map((fmt) => (
              <button key={fmt} type="button" className="btn btn-ghost" onClick={() => download(viewing, fmt)}>
                Download {fmt === 'xlsx' ? 'Excel' : fmt.toUpperCase()}
              </button>
            ))}
          </div>
        </Modal>
      )}
    </div>
  )
}
