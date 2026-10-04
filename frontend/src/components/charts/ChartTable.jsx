import { useState } from 'react'

// The table-view twin every chart ships with - the values a chart shows, readable
// without hovering, colour or a pointer.
export default function ChartTable({ columns, rows, caption = 'Data table' }) {
  const [open, setOpen] = useState(false)
  if (!rows.length) return null
  return (
    <div className="viz-table-toggle">
      <button type="button" className="btn-link" onClick={() => setOpen((prev) => !prev)} aria-expanded={open}>
        {open ? 'Hide table' : 'View as table'}
      </button>
      {open && (
        <div className="table-wrapper">
          <table className="table table-compact">
            <caption className="sr-only">{caption}</caption>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column.key} className={column.numeric ? 'num' : ''}>
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.key ?? index}>
                  {columns.map((column) => (
                    <td key={column.key} className={column.numeric ? 'num' : ''}>
                      {column.format ? column.format(row[column.key], row) : row[column.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
