import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { getBrandProfile } from '../api/brand'
import { getBrandContext } from '../api/aiStrategy'
import { listCalendarItems } from '../api/contentCalendar'
import { listGenerationRequests } from '../api/creativeGeneration'
import { getCompany, getMyCompany } from '../api/companies'
import { visibleModules } from '../context/CompanyWorkspaceContext'
import { WorkflowContext, computeWorkflow, visibleSteps } from '../context/workflow'

function hasBrandBasics(profile) {
  if (!profile) return false
  return Boolean(
    profile.logo ||
      (profile.brand_colors && profile.brand_colors.length > 0) ||
      profile.brand_voice ||
      profile.tone ||
      profile.visual_style,
  )
}

async function fetchSignals(companyId, canSee) {
  const brand = canSee('brand')
    ? getBrandProfile(companyId).then(hasBrandBasics, () => null)
    : Promise.resolve(null)
  const strategy = canSee('ai-strategy')
    ? getBrandContext(companyId).then(
        () => true,
        (err) => (err?.response?.status === 404 ? false : null),
      )
    : Promise.resolve(null)
  const calendar = canSee('calendar')
    ? listCalendarItems(companyId).then(
        (data) => {
          const counts = {}
          for (const item of data.results || []) counts[item.status] = (counts[item.status] || 0) + 1
          return { total: data.count ?? (data.results || []).length, sampled: (data.results || []).length, counts }
        },
        () => null,
      )
    : Promise.resolve(null)
  const creatives = canSee('creative-generation')
    ? listGenerationRequests(companyId).then((data) => (data.count ?? (data.results || []).length) > 0, () => null)
    : Promise.resolve(null)

  const [brandReady, strategyReady, calendarData, hasCreativeRequests] = await Promise.all([
    brand, strategy, calendar, creatives,
  ])
  return { brandReady, strategyReady, calendar: calendarData, hasCreativeRequests }
}

/**
 * Loads the workflow progress of one company (the one in the URL for an admin, the
 * client's own company for a client) and shares it with the sidebar, the workspace
 * stepper and the dashboards. Refreshes whenever the page changes, so finishing a step
 * and moving on shows the next one unlocked.
 */
export default function WorkflowProvider({ companyId, isAdmin, permissions, children }) {
  const location = useLocation()
  const [signals, setSignals] = useState(null)
  const [loadedFor, setLoadedFor] = useState(null)
  const [company, setCompany] = useState(null)
  const requestRef = useRef(0)

  const permissionKey = (permissions || []).join(',')
  const visiblePaths = useMemo(
    () => visibleModules(isAdmin, permissionKey ? permissionKey.split(',') : []).map((module) => module.path),
    [isAdmin, permissionKey],
  )

  const refresh = useCallback(() => {
    if (!companyId) return
    const requestId = ++requestRef.current
    const canSee = (path) => isAdmin || visiblePaths.includes(path)
    fetchSignals(companyId, canSee)
      .then((result) => {
        if (requestRef.current !== requestId) return
        setSignals(result)
        setLoadedFor(companyId)
      })
      .catch(() => {})
  }, [companyId, isAdmin, visiblePaths])

  useEffect(() => {
    refresh()
  }, [refresh, location.pathname])

  useEffect(() => {
    if (!companyId) return undefined
    let cancelled = false
    const load = isAdmin ? getCompany(companyId) : getMyCompany()
    load.then((data) => !cancelled && setCompany(data)).catch(() => !cancelled && setCompany(null))
    return () => {
      cancelled = true
    }
  }, [companyId, isAdmin])

  const value = useMemo(() => {
    const current = loadedFor === companyId ? signals : null
    return {
      companyId,
      company: company && String(company.id) === String(companyId) ? company : null,
      workflow: companyId ? computeWorkflow(current) : null,
      steps: visibleSteps(isAdmin, visiblePaths),
      refresh,
    }
  }, [companyId, company, loadedFor, signals, isAdmin, visiblePaths, refresh])

  return <WorkflowContext.Provider value={value}>{children}</WorkflowContext.Provider>
}
