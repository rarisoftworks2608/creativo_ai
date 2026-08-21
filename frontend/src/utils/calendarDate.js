const MONTH_LABELS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

const WEEKDAY_LABELS_LONG = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

export function toDateKey(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export function toMonthKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

export function formatMonthLabel(date) {
  return `${MONTH_LABELS[date.getMonth()]} ${date.getFullYear()}`
}

export function formatDayLabel(date) {
  return `${WEEKDAY_LABELS_LONG[date.getDay()]}, ${MONTH_LABELS[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`
}

export function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

export function addMonths(date, delta) {
  return new Date(date.getFullYear(), date.getMonth() + delta, 1)
}

export function isSameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
}

/** Always 6 full weeks (42 days) for a stable grid height across months. */
export function buildMonthWeeks(monthDate) {
  const first = startOfMonth(monthDate)
  const gridStart = new Date(first)
  gridStart.setDate(gridStart.getDate() - gridStart.getDay())

  const weeks = []
  const cursor = new Date(gridStart)
  for (let w = 0; w < 6; w++) {
    const week = []
    for (let d = 0; d < 7; d++) {
      week.push(new Date(cursor))
      cursor.setDate(cursor.getDate() + 1)
    }
    weeks.push(week)
  }
  return weeks
}
