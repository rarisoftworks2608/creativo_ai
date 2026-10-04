// Shared display formatting used by the publishing / analytics / reports / subscription pages.

const numberFormatter = new Intl.NumberFormat('en-US')
const compactFormatter = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })

export function formatNumber(value) {
  if (value === null || value === undefined || value === '') return '—'
  return numberFormatter.format(value)
}

export function formatCompact(value) {
  if (value === null || value === undefined || value === '') return '—'
  return Math.abs(value) >= 10000 ? compactFormatter.format(value) : numberFormatter.format(value)
}

export function formatPercent(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return `${Number(value).toFixed(digits)}%`
}

export function formatMoney(value, currency = 'INR') {
  if (value === null || value === undefined || value === '') return '—'
  try {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 2 }).format(Number(value))
  } catch {
    return `${currency} ${Number(value).toFixed(2)}`
  }
}

export function formatDate(value) {
  if (!value) return '—'
  const date = typeof value === 'string' && value.length === 10 ? new Date(`${value}T00:00:00`) : new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export function formatShortDay(isoDate) {
  const date = new Date(`${isoDate}T00:00:00`)
  return date.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export function timeAgo(value) {
  if (!value) return ''
  const seconds = Math.round((Date.now() - new Date(value).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  return `${days} d ago`
}

// <input type="datetime-local"> wants local "YYYY-MM-DDTHH:mm" without a timezone.
export function toLocalInputValue(value) {
  const date = value ? new Date(value) : new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function isoDate(date) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function formatBytes(bytes) {
  if (!bytes) return '0 MB'
  const mb = bytes / (1024 * 1024)
  return mb >= 1024 ? `${(mb / 1024).toFixed(2)} GB` : `${mb.toFixed(1)} MB`
}

export const PLATFORM_LABELS = {
  instagram: 'Instagram',
  facebook: 'Facebook',
  linkedin: 'LinkedIn',
  twitter: 'X (Twitter)',
  pinterest: 'Pinterest',
}

export function platformLabel(value) {
  return PLATFORM_LABELS[value] || value || '—'
}

// Date-range presets shared by the analytics and reports pages.
export function rangePreset(key) {
  const today = new Date()
  const end = isoDate(today)
  const daysAgo = (n) => {
    const d = new Date(today)
    d.setDate(d.getDate() - n)
    return isoDate(d)
  }
  switch (key) {
    case '7d':
      return { start: daysAgo(6), end }
    case '90d':
      return { start: daysAgo(89), end }
    case 'month':
      return { start: isoDate(new Date(today.getFullYear(), today.getMonth(), 1)), end }
    case 'last_month': {
      const first = new Date(today.getFullYear(), today.getMonth() - 1, 1)
      const last = new Date(today.getFullYear(), today.getMonth(), 0)
      return { start: isoDate(first), end: isoDate(last) }
    }
    case '30d':
    default:
      return { start: daysAgo(29), end }
  }
}
