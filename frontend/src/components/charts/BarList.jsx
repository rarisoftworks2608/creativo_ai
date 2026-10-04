import { useState } from 'react'

/**
 * Horizontal bars for comparing one measure across categories (platforms, content
 * types, companies). One series, so every bar uses series slot 1; the value sits at
 * the bar tip in text ink; each bar has its own hover/focus tooltip with the detail.
 */
export default function BarList({ rows, formatValue = (v) => v, detail, ariaLabel = 'Bar chart' }) {
  const [hovered, setHovered] = useState(null)
  const max = Math.max(0, ...rows.map((row) => row.value || 0)) || 1

  if (!rows.length) return null

  return (
    <div className="viz viz-bars" role="list" aria-label={ariaLabel}>
      {rows.map((row, index) => {
        const percent = Math.max(((row.value || 0) / max) * 100, row.value ? 1.5 : 0)
        return (
          <div
            key={row.key ?? row.label}
            className={`viz-bar-row ${hovered === index ? 'viz-bar-row-active' : ''}`}
            role="listitem"
            tabIndex={0}
            onPointerEnter={() => setHovered(index)}
            onPointerLeave={() => setHovered(null)}
            onFocus={() => setHovered(index)}
            onBlur={() => setHovered(null)}
          >
            <div className="viz-bar-label">{row.label}</div>
            <div className="viz-bar-track">
              <div className="viz-bar" style={{ width: `${percent}%` }} />
              <span className="viz-bar-value">{formatValue(row.value)}</span>
            </div>
            {hovered === index && detail && (
              <div className="viz-tooltip viz-tooltip-inline">
                <div className="viz-tooltip-row">
                  <span className="viz-key-box" aria-hidden="true" />
                  <strong>{formatValue(row.value)}</strong>
                  <span className="viz-tooltip-series">{row.label}</span>
                </div>
                <div className="viz-tooltip-label">{detail(row)}</div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
