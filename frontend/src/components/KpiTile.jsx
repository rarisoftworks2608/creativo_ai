import Sparkline from './charts/Sparkline'

/**
 * Stat tile: label · value · optional signed delta vs a named period · optional sparkline.
 * The delta carries direction with an arrow + sign + words, never colour alone.
 */
export default function KpiTile({ label, value, change, changeLabel = 'vs previous period', hint, trend, upIsGood = true }) {
  let deltaClass = 'kpi-delta-flat'
  if (typeof change === 'number' && change !== 0) {
    const good = change > 0 === upIsGood
    deltaClass = good ? 'kpi-delta-good' : 'kpi-delta-bad'
  }
  return (
    <div className="kpi-tile">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {typeof change === 'number' ? (
        <div className={`kpi-delta ${deltaClass}`}>
          <span aria-hidden="true">{change > 0 ? '▲' : change < 0 ? '▼' : '■'}</span>
          {change > 0 ? '+' : ''}
          {change.toFixed(1)}% <span className="kpi-delta-period">{changeLabel}</span>
        </div>
      ) : (
        hint && <div className="kpi-hint">{hint}</div>
      )}
      {trend && trend.length > 1 && <Sparkline values={trend} ariaLabel={`${label} trend`} />}
    </div>
  )
}
