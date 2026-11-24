import { createContext, useContext } from 'react'

/**
 * The content workflow a company moves through, in order. Each step groups one or more
 * company modules (route paths under /companies/:id/). A step unlocks once the step it
 * depends on has produced something - or as soon as it has data of its own, so a company
 * that already has content is never locked out of it.
 */
export const WORKFLOW_STEPS = [
  {
    key: 'brand', number: 1, title: 'Brand', icon: 'image',
    hint: 'Logo, colours and tone of voice',
    modules: [{ path: 'brand', label: 'Brand profile' }],
  },
  {
    key: 'strategy', number: 2, title: 'Strategy', icon: 'sparkle', requires: 'brand',
    hint: 'AI brand context and content ideas',
    modules: [{ path: 'ai-strategy', label: 'AI strategy' }],
  },
  {
    key: 'calendar', number: 3, title: 'Calendar', icon: 'calendar', requires: 'brand',
    hint: 'Plan the posts for the month',
    modules: [{ path: 'calendar', label: 'Content calendar' }],
  },
  {
    key: 'create', number: 4, title: 'Create', icon: 'wand', requires: 'calendar',
    hint: 'Generate creatives and videos',
    modules: [
      { path: 'creative-generation', label: 'Image creatives' },
      { path: 'video-generation', label: 'Videos' },
      { path: 'media-library', label: 'Media library', alwaysOpen: true },
    ],
  },
  {
    key: 'review', number: 5, title: 'Review', icon: 'check', requires: 'create',
    hint: 'Approve or request changes',
    modules: [
      { path: 'approvals', label: 'Approvals' },
      { path: 'whatsapp', label: 'WhatsApp alerts', alwaysOpen: true },
    ],
  },
  {
    key: 'publish', number: 6, title: 'Publish', icon: 'send', requires: 'review',
    hint: 'Schedule and post approved content',
    modules: [
      { path: 'publishing', label: 'Publishing' },
      { path: 'social-accounts', label: 'Social accounts', alwaysOpen: true },
    ],
  },
  {
    key: 'results', number: 7, title: 'Results', icon: 'chart', requires: 'publish',
    hint: 'Analytics and monthly reports',
    modules: [
      { path: 'analytics', label: 'Analytics' },
      { path: 'reports', label: 'Reports' },
    ],
  },
]

// What a step needs before it opens, phrased for the person looking at a locked step.
export const LOCK_REASONS = {
  strategy: 'Add the brand details first - the strategy is built from them.',
  calendar: 'Add the brand details first so the plan matches the brand.',
  create: 'Plan at least one post in the calendar first.',
  review: 'Generate a creative or video first - there is nothing to review yet.',
  publish: 'Approve at least one piece of content first.',
  results: 'Publish at least one post first - results appear after it goes live.',
}

// Modules that sit outside the sequence.
export const WORKSPACE_EXTRAS = [
  { path: '', label: 'Overview', adminOnly: true, end: true },
  { path: 'subscription', label: 'Plan & usage', page: 'subscription' },
]

/** The first module of a step that should open when the step itself is clicked. */
export function stepEntry(step) {
  return step.modules.find((module) => !module.alwaysOpen) || step.modules[0]
}

export function moduleForPath(path) {
  for (const step of WORKFLOW_STEPS) {
    const module = step.modules.find((m) => m.path === path)
    if (module) return { step, module }
  }
  return null
}

const GENERATED_STATUSES = ['generated', 'pending_approval', 'approved', 'rejected', 'published']

/**
 * Turns the raw signals fetched for a company into a status per step:
 * 'done' | 'current' (the next thing to do) | 'open' | 'locked'.
 * A signal of `null` means "unknown" (the request failed or isn't allowed), and an
 * unknown signal never locks anything.
 */
export function computeWorkflow(signals) {
  if (!signals) return null
  const { brandReady, strategyReady, calendar, hasCreativeRequests } = signals

  const counts = calendar?.counts || {}
  const total = calendar?.total ?? null
  // Only the first page of items is counted; with more than that, don't guess.
  const partial = calendar ? calendar.total > calendar.sampled : false
  const known = calendar !== null && !partial
  const sum = (statuses) => statuses.reduce((acc, status) => acc + (counts[status] || 0), 0)

  const done = {
    brand: brandReady === null ? true : brandReady,
    strategy: strategyReady === null ? true : strategyReady,
    calendar: total === null ? true : total > 0,
    create: !known || sum(GENERATED_STATUSES) > 0 || hasCreativeRequests === true,
    review: !known || (sum(['approved', 'published']) > 0 && (counts.pending_approval || 0) === 0),
    publish: !known || (counts.published || 0) > 0,
    results: false,
  }
  // Data that means a step has been used, even if its own "done" bar isn't met yet.
  const hasData = {
    ...done,
    review: !known || sum(['pending_approval', 'approved', 'rejected', 'published']) > 0,
    publish: !known || sum(['approved', 'published']) > 0,
    results: !known || (counts.published || 0) > 0,
  }
  const prerequisiteMet = {
    brand: true,
    strategy: done.brand,
    calendar: done.brand,
    create: done.calendar || hasData.create,
    review: hasData.create,
    publish: sum(['approved', 'published']) > 0 || !known,
    results: (counts.published || 0) > 0 || !known,
  }

  const steps = {}
  let currentAssigned = false
  for (const step of WORKFLOW_STEPS) {
    const unlocked = prerequisiteMet[step.key] || hasData[step.key]
    let status
    if (!unlocked) status = 'locked'
    else if (done[step.key]) status = 'done'
    else if (!currentAssigned) {
      status = 'current'
      currentAssigned = true
    } else status = 'open'
    steps[step.key] = { status, locked: !unlocked, reason: unlocked ? '' : LOCK_REASONS[step.key] }
  }
  const pendingApproval = counts.pending_approval || 0
  return { steps, pendingApproval, total }
}

export function stepForModule(path) {
  return WORKFLOW_STEPS.find((step) => step.modules.some((module) => module.path === path)) || null
}

/** Steps (and their modules) this viewer may see, given client page permissions. */
export function visibleSteps(isAdmin, visiblePaths) {
  return WORKFLOW_STEPS.map((step) => ({
    ...step,
    modules: step.modules.filter((module) => isAdmin || visiblePaths.includes(module.path)),
  })).filter((step) => step.modules.length > 0)
}

export const WorkflowContext = createContext(null)

export function useWorkflow() {
  return useContext(WorkflowContext)
}
