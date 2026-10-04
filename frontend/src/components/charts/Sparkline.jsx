// Tiny trend line for stat tiles - de-emphasis stroke with the current point accented.
export default function Sparkline({ values, width = 120, height = 32, ariaLabel = 'Trend' }) {
  const clean = values.filter((v) => v !== null && v !== undefined)
  if (clean.length < 2) return null
  const min = Math.min(...clean)
  const max = Math.max(...clean)
  const range = max - min || 1
  const step = width / (clean.length - 1)
  const points = clean.map((v, i) => [i * step, height - 3 - ((v - min) / range) * (height - 6)])
  const path = points.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const [lastX, lastY] = points[points.length - 1]
  return (
    <svg className="viz viz-spark" width={width} height={height} role="img" aria-label={ariaLabel}>
      <path d={path} className="viz-spark-stroke" />
      <circle cx={lastX} cy={lastY} r={3} className="viz-dot" />
    </svg>
  )
}
