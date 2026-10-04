import { useMemo, useState } from 'react'
import useElementWidth from './useElementWidth'

function niceMax(value) {
  if (value <= 0) return 1
  const exponent = 10 ** Math.floor(Math.log10(value))
  const fraction = value / exponent
  const nice = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 2.5 ? 2.5 : fraction <= 5 ? 5 : 10
  return nice * exponent
}

const tickFormatter = new Intl.NumberFormat('en-US')

/**
 * Single-series trend line (2px, 10% area wash) with a crosshair tooltip that snaps to
 * the nearest point, keyboard support (focus + arrow keys), and a labelled peak.
 * One series, so no legend - the card title names what is plotted.
 */
export default function LineChart({
  data,
  height = 220,
  formatValue = (v) => tickFormatter.format(v),
  formatLabel = (l) => l,
  ariaLabel = 'Trend chart',
  seriesName = 'Value',
}) {
  const [containerRef, width] = useElementWidth()
  const [activeIndex, setActiveIndex] = useState(null)

  const margin = { top: 16, right: 16, bottom: 28, left: 48 }
  const plotWidth = Math.max(width - margin.left - margin.right, 40)
  const plotHeight = height - margin.top - margin.bottom

  const { points, yMax, ticks, peakIndex } = useMemo(() => {
    const max = niceMax(Math.max(0, ...data.map((d) => d.value || 0)))
    const step = data.length > 1 ? plotWidth / (data.length - 1) : 0
    const pts = data.map((d, i) => ({
      x: data.length > 1 ? i * step : plotWidth / 2,
      y: plotHeight - ((d.value || 0) / max) * plotHeight,
      ...d,
    }))
    let peak = null
    data.forEach((d, i) => {
      if ((d.value || 0) > 0 && (peak === null || d.value > data[peak].value)) peak = i
    })
    return { points: pts, yMax: max, ticks: [0, 0.25, 0.5, 0.75, 1].map((t) => t * max), peakIndex: peak }
  }, [data, plotWidth, plotHeight])

  if (!data.length) return <div className="viz viz-line" ref={containerRef} />

  const linePath = points.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
  const areaPath = `${linePath} L${points[points.length - 1].x.toFixed(1)},${plotHeight} L${points[0].x.toFixed(1)},${plotHeight} Z`
  const labelEvery = Math.max(1, Math.ceil(data.length / Math.max(2, Math.floor(plotWidth / 80))))

  function indexFromPointer(event) {
    const rect = event.currentTarget.getBoundingClientRect()
    const x = event.clientX - rect.left - margin.left
    if (data.length === 1) return 0
    const step = plotWidth / (data.length - 1)
    return Math.min(data.length - 1, Math.max(0, Math.round(x / step)))
  }

  function handleKeyDown(event) {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault()
      const delta = event.key === 'ArrowRight' ? 1 : -1
      setActiveIndex((current) => Math.min(data.length - 1, Math.max(0, (current ?? (delta > 0 ? -1 : data.length)) + delta)))
    } else if (event.key === 'Escape') {
      setActiveIndex(null)
    }
  }

  const active = activeIndex !== null ? points[activeIndex] : null
  const tooltipLeft = active ? Math.min(Math.max(active.x + margin.left, 70), width - 70) : 0

  return (
    <div className="viz viz-line" ref={containerRef}>
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={ariaLabel}
        tabIndex={0}
        onKeyDown={handleKeyDown}
        onBlur={() => setActiveIndex(null)}
        onPointerMove={(event) => setActiveIndex(indexFromPointer(event))}
        onPointerLeave={() => setActiveIndex(null)}
      >
        <g transform={`translate(${margin.left},${margin.top})`}>
          {ticks.map((tick) => {
            const y = plotHeight - (tick / yMax) * plotHeight
            return (
              <g key={tick}>
                <line x1={0} x2={plotWidth} y1={y} y2={y} className={tick === 0 ? 'viz-baseline' : 'viz-grid'} />
                <text x={-8} y={y} dy="0.32em" textAnchor="end" className="viz-tick">
                  {tickFormatter.format(Math.round(tick))}
                </text>
              </g>
            )
          })}
          {points.map((p, i) =>
            i % labelEvery === 0 || i === points.length - 1 ? (
              <text key={p.label} x={p.x} y={plotHeight + 18} textAnchor="middle" className="viz-tick">
                {formatLabel(p.label)}
              </text>
            ) : null,
          )}
          <path d={areaPath} className="viz-area" />
          <path d={linePath} className="viz-stroke" />
          {peakIndex !== null && activeIndex === null && (
            <g>
              <circle cx={points[peakIndex].x} cy={points[peakIndex].y} r={4} className="viz-dot" />
              <text
                x={points[peakIndex].x}
                y={points[peakIndex].y - 10}
                textAnchor={points[peakIndex].x > plotWidth - 40 ? 'end' : points[peakIndex].x < 40 ? 'start' : 'middle'}
                className="viz-label"
              >
                {formatValue(points[peakIndex].value)}
              </text>
            </g>
          )}
          {active && (
            <g>
              <line x1={active.x} x2={active.x} y1={0} y2={plotHeight} className="viz-crosshair" />
              <circle cx={active.x} cy={active.y} r={4} className="viz-dot" />
            </g>
          )}
        </g>
      </svg>
      {active && (
        <div className="viz-tooltip" style={{ left: tooltipLeft, top: margin.top }}>
          <div className="viz-tooltip-row">
            <span className="viz-key-line" aria-hidden="true" />
            <strong>{formatValue(active.value)}</strong>
            <span className="viz-tooltip-series">{seriesName}</span>
          </div>
          <div className="viz-tooltip-label">{formatLabel(active.label)}</div>
        </div>
      )}
    </div>
  )
}
