// Renders a report's format-neutral document (KPIs + tabular sections) in the browser,
// the same content the PDF / Excel / CSV exports contain.
export default function ReportViewer({ document }) {
  if (!document?.title) return <p className="page-subtitle">This report has no content yet.</p>
  return (
    <div className="report-viewer">
      <p className="page-subtitle">{document.subtitle}</p>
      {document.kpis?.length > 0 && (
        <div className="kpi-grid kpi-grid-compact">
          {document.kpis.map((kpi) => (
            <div className="kpi-tile" key={kpi.label}>
              <div className="kpi-label">{kpi.label}</div>
              <div className="kpi-value">{typeof kpi.value === 'number' ? kpi.value.toLocaleString() : kpi.value}</div>
              {kpi.hint && <div className="kpi-hint">{kpi.hint}</div>}
            </div>
          ))}
        </div>
      )}
      {document.sections?.map((section) => (
        <section key={section.title} className="report-section">
          <h3 className="section-title">{section.title}</h3>
          {section.description && <p className="page-subtitle">{section.description}</p>}
          {section.rows.length === 0 ? (
            <p className="page-subtitle">No data for this period.</p>
          ) : (
            <div className="table-wrapper">
              <table className="table table-compact">
                <thead>
                  <tr>
                    {section.columns.map((column) => (
                      <th key={column}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {section.rows.map((row, index) => (
                    <tr key={index}>
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex} className={typeof cell === 'number' ? 'num' : ''}>
                          {typeof cell === 'string' && cell.startsWith('http') ? (
                            <a href={cell} target="_blank" rel="noreferrer">
                              link ↗
                            </a>
                          ) : typeof cell === 'number' ? (
                            cell.toLocaleString()
                          ) : (
                            cell
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ))}
    </div>
  )
}
