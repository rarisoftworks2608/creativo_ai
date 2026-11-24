import { Suspense, useEffect, useState } from 'react'
import { Link, Outlet, useLocation, useParams } from 'react-router-dom'
import { getCompany, getMyCompany } from '../api/companies'
import { useAuth } from '../context/AuthContext'
import { CompanyWorkspaceContext } from '../context/CompanyWorkspaceContext'
import { moduleForPath, stepEntry, useWorkflow } from '../context/workflow'
import ICONS from './DashboardIcons'

const STATUS_TEXT = { done: 'Completed', current: 'Next step', open: 'In progress', locked: 'Locked' }

/**
 * Wraps every /companies/:id/... page. Navigation lives in the sidebar (the company's
 * numbered workflow); here each workflow page gets a slim "Step N of 7" strip, a locked
 * screen when its step isn't available yet, and a previous / next step footer.
 */
export default function CompanyLayout() {
  const { id } = useParams()
  const location = useLocation()
  const { isAdmin } = useAuth()
  const workflowCtx = useWorkflow()
  const [company, setCompany] = useState(null)
  const [permissions, setPermissions] = useState([])
  const [overrides, setOverrides] = useState([])

  useEffect(() => {
    let cancelled = false
    setOverrides([])
    const load = isAdmin ? getCompany(id) : getMyCompany()
    load
      .then((data) => {
        if (cancelled) return
        setCompany(data)
        setPermissions(data.page_permissions || [])
      })
      .catch(() => {
        if (!cancelled) setCompany(null)
      })
    return () => {
      cancelled = true
    }
  }, [id, isAdmin])

  const base = `/companies/${id}`
  const segment = location.pathname.slice(base.length).split('/').filter(Boolean)[0] || ''
  const steps = workflowCtx?.steps || []
  const workflow = workflowCtx && String(workflowCtx.companyId) === String(id) ? workflowCtx.workflow : null
  const found = moduleForPath(segment)
  const index = found ? steps.findIndex((step) => step.key === found.step.key) : -1
  const step = index >= 0 ? steps[index] : null
  const state = step ? workflow?.steps[step.key] : null
  const status = state?.status || 'open'

  const isLocked = Boolean(step && state?.locked && !found.module.alwaysOpen && !overrides.includes(step.key))
  const prevStep = index > 0 ? steps[index - 1] : null
  const nextStep = index >= 0 && index < steps.length - 1 ? steps[index + 1] : null
  const nextLocked = nextStep && workflow?.steps[nextStep.key]?.locked

  return (
    <CompanyWorkspaceContext.Provider value={{ company, permissions }}>
      <div className="company-workspace">
        {step && (
          <div className="step-strip">
            <span className="step-strip-label">
              Step {index + 1} of {steps.length}
            </span>
            <span className="step-strip-title">{step.title}</span>
            <span className={`step-chip step-chip-${status}`}>{STATUS_TEXT[status]}</span>
            <ol className="step-dots" aria-hidden="true">
              {steps.map((item) => (
                <li
                  key={item.key}
                  className={`step-dot step-dot-${workflow?.steps[item.key]?.status || 'open'} ${item.key === step.key ? 'is-here' : ''}`}
                />
              ))}
            </ol>
          </div>
        )}

        {isLocked ? (
          <div className="card step-locked">
            <span className="step-locked-icon" aria-hidden="true">{ICONS.lock}</span>
            <h2>
              Step {step.number} · {step.title} is locked
            </h2>
            <p>{state.reason}</p>
            <div className="step-locked-actions">
              {prevStep && (
                <Link to={`${base}/${stepEntry(prevStep).path}`} className="btn btn-primary">
                  Go to step {prevStep.number} · {prevStep.title}
                </Link>
              )}
              {isAdmin && (
                <button type="button" className="btn btn-ghost" onClick={() => setOverrides((prev) => [...prev, step.key])}>
                  Open anyway
                </button>
              )}
            </div>
          </div>
        ) : (
          <Suspense fallback={<div className="page-loading">Loading…</div>}>
            <Outlet />
          </Suspense>
        )}

        {step && !isLocked && (prevStep || nextStep) && (
          <div className="step-footer">
            {prevStep ? (
              <Link to={`${base}/${stepEntry(prevStep).path}`} className="step-footer-link step-footer-prev">
                <span className="step-footer-icon" aria-hidden="true">{ICONS.arrowLeft}</span>
                <span>
                  <small>Previous step</small>
                  {prevStep.number}. {prevStep.title}
                </span>
              </Link>
            ) : (
              <span />
            )}
            {nextStep &&
              (nextLocked ? (
                <span className="step-footer-link step-footer-next is-locked" title={workflow.steps[nextStep.key].reason}>
                  <span>
                    <small>Next step · locked</small>
                    {nextStep.number}. {nextStep.title}
                  </span>
                  <span className="step-footer-icon" aria-hidden="true">{ICONS.lock}</span>
                </span>
              ) : (
                <Link to={`${base}/${stepEntry(nextStep).path}`} className="step-footer-link step-footer-next">
                  <span>
                    <small>Next step</small>
                    {nextStep.number}. {nextStep.title}
                  </span>
                  <span className="step-footer-icon" aria-hidden="true">{ICONS.arrowRight}</span>
                </Link>
              ))}
          </div>
        )}
      </div>
    </CompanyWorkspaceContext.Provider>
  )
}
