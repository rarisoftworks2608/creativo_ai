import { formatDate, formatDateTime } from '../utils/format'

// Report rows with status + PDF / Excel / CSV downloads and admin actions.
export default function ReportList({ reports, canManage, busyId, onView, onDownload, onSend, onRegenerate, onDelete }) {
  if (!reports.length) {
    return (
      <div className="card">
        <div className="empty-state">
          <p>No reports yet.</p>
        </div>
      </div>
    )
  }
  return (
    <div className="report-list">
      {reports.map((report) => (
        <div className="card report-row" key={report.id}>
          <div className="report-row-main">
            <div className="report-row-title">
              <strong>{report.title || report.report_type_display}</strong>
              <span className={`badge status-badge report-status-${report.status}`}>{report.status_display}</span>
              {report.is_automated && <span className="badge status-badge status-scheduled">Automatic</span>}
            </div>
            <div className="page-subtitle">
              {report.report_type_display} · {formatDate(report.period_start)} – {formatDate(report.period_end)}
              {report.generated_at ? ` · generated ${formatDateTime(report.generated_at)}` : ''}
              {report.emailed_at ? ' · emailed' : ''}
              {report.whatsapp_sent_at ? ' · sent on WhatsApp' : ''}
            </div>
            {report.status === 'failed' && report.error && <div className="cell-error">{report.error}</div>}
          </div>
          <div className="report-row-actions">
            {report.status === 'ready' && (
              <>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => onView(report)}>
                  View
                </button>
                {report.formats.map((fmt) => (
                  <button key={fmt} type="button" className="btn btn-ghost btn-sm" onClick={() => onDownload(report, fmt)}>
                    {fmt === 'xlsx' ? 'Excel' : fmt.toUpperCase()}
                  </button>
                ))}
              </>
            )}
            {(report.status === 'pending' || report.status === 'generating') && <span className="page-subtitle">Generating…</span>}
            {canManage && report.status === 'ready' && onSend && (
              <button type="button" className="btn btn-ghost btn-sm" disabled={busyId === report.id} onClick={() => onSend(report)}>
                Send to client
              </button>
            )}
            {canManage && (
              <>
                <button type="button" className="btn-link" disabled={busyId === report.id} onClick={() => onRegenerate(report)}>
                  Regenerate
                </button>
                <button type="button" className="btn-link btn-link-danger" disabled={busyId === report.id} onClick={() => onDelete(report)}>
                  Delete
                </button>
              </>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
