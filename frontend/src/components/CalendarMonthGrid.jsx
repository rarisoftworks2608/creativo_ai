import { buildMonthWeeks, isSameDay, toDateKey } from '../utils/calendarDate'

const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MAX_VISIBLE_PER_DAY = 3

export default function CalendarMonthGrid({ month, itemsByDate, onDayClick, onItemClick, onMoreClick }) {
  const weeks = buildMonthWeeks(month)
  const today = new Date()

  return (
    <div className="cal-grid">
      <div className="cal-weekday-row">
        {WEEKDAY_LABELS.map((label) => (
          <div key={label} className="cal-weekday">{label}</div>
        ))}
      </div>

      {weeks.map((week, weekIndex) => (
        <div className="cal-week" key={weekIndex}>
          {week.map((day) => {
            const key = toDateKey(day)
            const dayItems = itemsByDate[key] || []
            const visible = dayItems.slice(0, MAX_VISIBLE_PER_DAY)
            const overflow = dayItems.length - visible.length
            const inMonth = day.getMonth() === month.getMonth()
            const isToday = isSameDay(day, today)

            return (
              <div
                key={key}
                className={`cal-day ${inMonth ? '' : 'cal-day-outside'} ${isToday ? 'cal-day-today' : ''}`}
                onClick={() => onDayClick(day)}
              >
                <div className="cal-day-number">{day.getDate()}</div>
                <div className="cal-day-items">
                  {visible.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="cal-chip"
                      onClick={(event) => {
                        event.stopPropagation()
                        onItemClick(item)
                      }}
                      title={item.topic}
                    >
                      <span className={`cal-chip-dot cal-dot-${item.status}`} aria-hidden="true" />
                      <span className="cal-chip-label">{item.topic}</span>
                    </button>
                  ))}
                  {overflow > 0 && (
                    <button
                      type="button"
                      className="cal-more"
                      onClick={(event) => {
                        event.stopPropagation()
                        onMoreClick(day, dayItems)
                      }}
                    >
                      +{overflow} more
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}
