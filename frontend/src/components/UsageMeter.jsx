import { formatNumber } from '../utils/format'

/**
 * Subscription usage meter: fill carries severity (normal -> warning at 80% -> danger at
 * 100%), the track is a lighter step of the same ramp, and the numbers are always
 * printed - colour never carries the state alone.
 */
export default function UsageMeter({ label, metric, unit = '' }) {
  if (!metric) return null
  const percent = metric.unlimited ? 0 : Math.min(metric.percentage, 100)
  const tone = metric.unlimited ? 'normal' : metric.percentage >= 100 ? 'danger' : metric.percentage >= 80 ? 'warning' : 'normal'
  const used = `${formatNumber(metric.used)}${unit ? ` ${unit}` : ''}`
  return (
    <div className={`meter meter-${tone}`}>
      <div className="meter-head">
        <span className="meter-label">{label}</span>
        <span className="meter-value">
          {metric.unlimited ? `${used} · unlimited` : `${used} / ${formatNumber(metric.limit)}${unit ? ` ${unit}` : ''}`}
        </span>
      </div>
      <div
        className="meter-track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={metric.unlimited ? 0 : Math.round(metric.percentage)}
      >
        <div className="meter-fill" style={{ width: `${percent}%` }} />
      </div>
      {!metric.unlimited && (
        <div className="meter-foot">
          {tone === 'danger' ? '⚠ Limit reached' : tone === 'warning' ? '⚠ Nearly used up' : `${formatNumber(metric.remaining)} left`}
          {' · '}
          {metric.percentage}%
        </div>
      )}
    </div>
  )
}
