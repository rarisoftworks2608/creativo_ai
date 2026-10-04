import { formatDateTime } from '../utils/format'

const TONE = {
  generated: 'info',
  regenerated: 'info',
  generation_failed: 'danger',
  variation_selected: 'neutral',
  approved: 'success',
  rejected: 'danger',
  regeneration_requested: 'warning',
  reminder_sent: 'neutral',
  scheduled: 'info',
  published: 'accent',
  publish_failed: 'danger',
}

// Approval / rejection / feedback / regeneration / publishing history (Epic 09: History).
export default function ReviewTimeline({ events }) {
  if (!events.length) return <p className="page-subtitle">No review activity yet.</p>
  return (
    <ol className="timeline">
      {events.map((event) => (
        <li key={event.id} className={`timeline-item timeline-${TONE[event.action] || 'neutral'}`}>
          <span className="timeline-dot" aria-hidden="true" />
          <div className="timeline-body">
            <div className="timeline-title">
              {event.action_display}
              <span className="timeline-meta">
                {event.actor_name}
                {event.actor_role !== 'system' ? ` (${event.actor_role})` : ''} · {formatDateTime(event.created_at)}
              </span>
            </div>
            {event.feedback && <p className="timeline-feedback">“{event.feedback}”</p>}
            {event.metadata?.platform && (
              <p className="timeline-meta">
                {event.metadata.platform}
                {event.metadata.url ? (
                  <>
                    {' · '}
                    <a href={event.metadata.url} target="_blank" rel="noreferrer">
                      view post
                    </a>
                  </>
                ) : null}
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}
