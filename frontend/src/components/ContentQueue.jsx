const QUEUED_STATUSES = ['draft', 'scheduled']

const STATUS_LABELS = { draft: 'Draft', scheduled: 'Scheduled' }

export default function ContentQueue({ items, onGenerateNow, generatingId, emptyMessage }) {
  const queued = items.filter((item) => QUEUED_STATUSES.includes(item.status))

  if (queued.length === 0) {
    return (
      <div className="card">
        <div className="card-header">
          <h2>Content queue</h2>
        </div>
        <div className="empty-state">
          <p>{emptyMessage}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-header">
        <h2>Content queue ({queued.length})</h2>
      </div>
      <p className="page-subtitle">
        Planned from the content calendar. Each one generates automatically on its scheduled date, or generate it now.
      </p>
      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Topic</th>
              <th>Format</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {queued.map((item) => (
              <tr key={item.id}>
                <td>{item.scheduled_date}</td>
                <td>{item.topic}</td>
                <td>{item.content_type}</td>
                <td>
                  <span className={`badge status-badge status-${item.status}`}>{STATUS_LABELS[item.status]}</span>
                </td>
                <td className="table-actions">
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={generatingId === item.id}
                    onClick={() => onGenerateNow(item.id)}
                  >
                    {generatingId === item.id ? 'Starting…' : 'Generate now'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
