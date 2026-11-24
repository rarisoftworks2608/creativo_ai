import { Link } from 'react-router-dom'
import { stepEntry, useWorkflow } from '../context/workflow'
import ICONS from './DashboardIcons'

const STATUS_TEXT = { done: 'Done', current: 'Next step', open: 'Ready', locked: 'Locked' }

/**
 * The company's workflow as a progress card: how far along it is, the one thing to do
 * next, and every step in order (locked ones explain what they're waiting for).
 */
export default function WorkflowJourney({ companyId, title = 'Content workflow' }) {
  const ctx = useWorkflow()
  if (!ctx || !companyId || String(ctx.companyId) !== String(companyId) || ctx.steps.length === 0) return null
  const { steps, workflow } = ctx
  const base = `/companies/${companyId}`
  const statusOf = (key) => workflow?.steps[key]?.status || 'open'
  const doneCount = steps.filter((step) => statusOf(step.key) === 'done').length
  const next = steps.find((step) => statusOf(step.key) === 'current') || steps.find((step) => statusOf(step.key) === 'open')
  const percent = Math.round((doneCount / steps.length) * 100)

  return (
    <section className="journey" aria-label={title}>
      <div className="journey-head">
        <div>
          <h2>{title}</h2>
          <p>
            {workflow
              ? `${doneCount} of ${steps.length} steps done${next ? ` · next: ${next.title.toLowerCase()}` : ''}`
              : 'Checking progress…'}
          </p>
        </div>
        {next && (
          <Link to={`${base}/${stepEntry(next).path}`} className="btn btn-primary">
            Continue: {next.number}. {next.title}
          </Link>
        )}
      </div>
      <div className="journey-progress" aria-hidden="true">
        <span style={{ width: `${percent}%` }} />
      </div>
      <ol className="journey-grid">
        {steps.map((step) => {
          const status = statusOf(step.key)
          const state = workflow?.steps[step.key]
          const inner = (
            <>
              <span className={`step-bubble step-bubble-${status}`} aria-hidden="true">
                {status === 'done' ? ICONS.check : status === 'locked' ? ICONS.lock : step.number}
              </span>
              <span className="journey-step-body">
                <strong>
                  {step.number}. {step.title}
                </strong>
                <span>{status === 'locked' ? state.reason : step.hint}</span>
                <span className="stepper-state">{STATUS_TEXT[status]}</span>
              </span>
            </>
          )
          return (
            <li key={step.key}>
              {status === 'locked' ? (
                <div className="journey-step journey-step-locked">{inner}</div>
              ) : (
                <Link to={`${base}/${stepEntry(step).path}`} className={`journey-step journey-step-${status}`}>
                  {inner}
                </Link>
              )}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
