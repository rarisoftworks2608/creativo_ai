import { useEffect, useRef, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { listCompanies } from '../api/companies'
import { WORKSPACE_EXTRAS, moduleForPath, stepEntry, useWorkflow } from '../context/workflow'
import ICONS from './DashboardIcons'

/* ---------------------------------------------------------------------------
   Global (admin) navigation - everything that spans companies.
   --------------------------------------------------------------------------- */

export const ADMIN_NAV = [
  {
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: 'home' },
      { to: '/companies', label: 'Companies', icon: 'building' },
    ],
  },
  {
    title: 'Work queue',
    items: [
      { to: '/approvals', label: 'Approvals', icon: 'check', badge: 'approvals' },
      { to: '/publishing', label: 'Publishing queue', icon: 'send' },
    ],
  },
  {
    title: 'Insights',
    items: [
      { to: '/analytics', label: 'Analytics', icon: 'chart' },
      { to: '/reports', label: 'Reports', icon: 'file' },
    ],
  },
  {
    title: 'Content library',
    collapsible: true,
    items: [
      { to: '/prompt-templates', label: 'Prompt library', icon: 'wand' },
      { to: '/music-library', label: 'Music library', icon: 'music' },
      { to: '/whatsapp', label: 'WhatsApp templates', icon: 'chat' },
    ],
  },
  {
    title: 'Organisation',
    collapsible: true,
    items: [
      { to: '/team', label: 'Team', icon: 'users' },
      { to: '/access', label: 'Access control', icon: 'shield' },
      { to: '/subscriptions', label: 'Subscriptions', icon: 'dollar' },
    ],
  },
  {
    title: 'System',
    collapsible: true,
    items: [
      { to: '/jobs', label: 'Background jobs', icon: 'clock' },
      { to: '/activity-log', label: 'Activity log', icon: 'file' },
      { to: '/system-health', label: 'System health', icon: 'alert' },
      { to: '/admin-settings', label: 'Platform settings', icon: 'settings' },
    ],
  },
]

export function NavItem({ item, badgeCount = 0 }) {
  return (
    <NavLink to={item.to} end={item.end} className={({ isActive }) => (isActive ? 'active' : '')}>
      <span className="nav-icon" aria-hidden="true">
        {ICONS[item.icon]}
      </span>
      <span className="nav-label">{item.label}</span>
      {badgeCount > 0 && <span className="nav-badge">{badgeCount > 99 ? '99+' : badgeCount}</span>}
    </NavLink>
  )
}

function NavGroup({ group, pendingApprovals, pathname }) {
  const containsActive = group.items.some((item) => pathname.startsWith(item.to))
  const [open, setOpen] = useState(false)
  const expanded = !group.collapsible || open || containsActive
  return (
    <div className="nav-group">
      {group.title &&
        (group.collapsible ? (
          <button
            type="button"
            className={`nav-group-title nav-group-toggle ${expanded ? 'is-open' : ''}`}
            onClick={() => setOpen((prev) => !prev)}
            aria-expanded={expanded}
          >
            {group.title}
            <span className="nav-group-chevron" aria-hidden="true">{ICONS.chevronDown}</span>
          </button>
        ) : (
          <div className="nav-group-title">{group.title}</div>
        ))}
      {expanded &&
        group.items.map((item) => (
          <NavItem key={item.to} item={item} badgeCount={item.badge === 'approvals' ? pendingApprovals : 0} />
        ))}
    </div>
  )
}

export function AdminNav({ pathname, pendingApprovals }) {
  return ADMIN_NAV.map((group, index) => (
    <NavGroup key={group.title || index} group={group} pendingApprovals={pendingApprovals} pathname={pathname} />
  ))
}

/* ---------------------------------------------------------------------------
   Company workspace navigation - the company's workflow, step by step, with
   each step's sub-sections nested underneath it.
   --------------------------------------------------------------------------- */

function CompanySwitcher({ company, isAdmin }) {
  const [open, setOpen] = useState(false)
  const [companies, setCompanies] = useState(null)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    if (companies === null) {
      listCompanies()
        .then((data) => setCompanies(data.results || []))
        .catch(() => setCompanies([]))
    }
    function onPointerDown(event) {
      if (ref.current && !ref.current.contains(event.target)) setOpen(false)
    }
    function onKeyDown(event) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open, companies])

  const name = company?.name || 'Loading…'
  const body = (
    <>
      <span className="co-switch-avatar" aria-hidden="true">{name.charAt(0).toUpperCase()}</span>
      <span className="co-switch-text">
        <span className="co-switch-name">{name}</span>
        <span className="co-switch-meta">{company?.industry || (isAdmin ? 'Company workspace' : 'Your workspace')}</span>
      </span>
    </>
  )

  if (!isAdmin) return <div className="co-switch">{body}</div>

  return (
    <div className="co-switch-wrap" ref={ref}>
      <button
        type="button"
        className="co-switch co-switch-btn"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {body}
        <span className="co-switch-chevron" aria-hidden="true">{ICONS.chevronDown}</span>
      </button>
      {open && (
        <div className="co-switch-menu" role="listbox" aria-label="Switch company">
          {companies === null && <div className="co-switch-empty">Loading…</div>}
          {companies?.length === 0 && <div className="co-switch-empty">No companies</div>}
          {companies?.map((item) => (
            <Link
              key={item.id}
              to={`/companies/${item.id}`}
              role="option"
              aria-selected={String(item.id) === String(company?.id)}
              className={`co-switch-option ${String(item.id) === String(company?.id) ? 'is-current' : ''}`}
              onClick={() => setOpen(false)}
            >
              <span className="co-switch-avatar sm" aria-hidden="true">{item.name.charAt(0).toUpperCase()}</span>
              <span className="nav-label">{item.name}</span>
            </Link>
          ))}
          <Link to="/companies" className="co-switch-all" onClick={() => setOpen(false)}>
            View all companies
          </Link>
        </div>
      )}
    </div>
  )
}

function StepNav({ step, state, base, segment, badge }) {
  const [open, setOpen] = useState(false)
  const status = state?.status || 'open'
  const isActive = step.modules.some((module) => module.path === segment)
  const multi = step.modules.length > 1
  const expanded = multi && (isActive || open)

  return (
    <div className={`nav-step-group ${isActive ? 'is-active' : ''}`}>
      <div className="nav-step-row">
        <Link
          to={`${base}/${stepEntry(step).path}`}
          className={`nav-step nav-step-${status} ${isActive && !multi ? 'active' : ''} ${isActive && multi ? 'is-parent' : ''}`}
          title={state?.reason || step.hint}
          aria-current={isActive && !multi ? 'page' : undefined}
        >
          <span className="nav-step-num" aria-hidden="true">
            {status === 'done' ? ICONS.check : status === 'locked' ? ICONS.lock : step.number}
          </span>
          <span className="nav-label">{step.title}</span>
          {badge > 0 && <span className="nav-badge">{badge}</span>}
        </Link>
        {multi && (
          <button
            type="button"
            className={`nav-step-toggle ${expanded ? 'is-open' : ''}`}
            onClick={() => setOpen((prev) => !prev)}
            aria-expanded={expanded}
            aria-label={`${expanded ? 'Hide' : 'Show'} ${step.title} sections`}
          >
            {ICONS.chevronDown}
          </button>
        )}
      </div>
      {expanded && (
        <div className="nav-sub">
          {step.modules.map((module) => (
            <Link
              key={module.path}
              to={`${base}/${module.path}`}
              className={`nav-sub-item ${segment === module.path ? 'active' : ''} ${
                state?.locked && !module.alwaysOpen ? 'is-locked' : ''
              }`}
              aria-current={segment === module.path ? 'page' : undefined}
            >
              {module.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

export function WorkspaceNav({ isAdmin, pathname }) {
  const ctx = useWorkflow()
  if (!ctx?.companyId) return null
  const { company, steps, workflow } = ctx
  const base = `/companies/${ctx.companyId}`
  const segment = pathname === base || pathname.startsWith(`${base}/`)
    ? pathname.slice(base.length).split('/').filter(Boolean)[0] || ''
    : null
  const doneCount = steps.filter((step) => workflow?.steps[step.key]?.status === 'done').length
  const permissions = company?.page_permissions || []
  const extras = WORKSPACE_EXTRAS.filter((extra) => (isAdmin ? true : !extra.adminOnly && permissions.includes(extra.page)))
  const plan = extras.find((extra) => extra.path === 'subscription')

  return (
    <>
      {isAdmin && (
        <Link to="/companies" className="ws-nav-back">
          <span className="nav-icon" aria-hidden="true">{ICONS.arrowLeft}</span>
          All companies
        </Link>
      )}
      <CompanySwitcher company={company} isAdmin={isAdmin} />

      <div className="nav-group">
        {isAdmin ? (
          <NavItem item={{ to: base, label: 'Overview', icon: 'home', end: true }} />
        ) : (
          <NavItem item={{ to: '/client', label: 'Dashboard', icon: 'home' }} />
        )}
      </div>

      {steps.length > 0 && (
        <div className="nav-group">
          <div className="nav-group-title nav-group-title-row">
            Content workflow
            <span className="nav-group-count">
              {doneCount}/{steps.length}
            </span>
          </div>
          <div className="nav-steps">
            {steps.map((step) => (
              <StepNav
                key={step.key}
                step={step}
                state={workflow?.steps[step.key]}
                base={base}
                segment={segment}
                badge={step.key === 'review' ? workflow?.pendingApproval || 0 : 0}
              />
            ))}
          </div>
        </div>
      )}

      <div className="nav-group">
        <div className="nav-group-title">{isAdmin ? 'Billing' : 'Account'}</div>
        {plan && <NavItem item={{ to: `${base}/subscription`, label: 'Plan & usage', icon: 'dollar' }} />}
        {!isAdmin && <NavItem item={{ to: '/settings', label: 'My account', icon: 'users' }} />}
      </div>
    </>
  )
}

/* ---------------------------------------------------------------------------
   Breadcrumb trail for the top bar.
   --------------------------------------------------------------------------- */

const GLOBAL_TITLES = Object.fromEntries(
  ADMIN_NAV.flatMap((group) => group.items.map((item) => [item.to, { label: item.label, group: group.title }])),
)
GLOBAL_TITLES['/settings'] = { label: 'My account' }
GLOBAL_TITLES['/client'] = { label: 'Dashboard' }

export function Breadcrumbs({ isAdmin, pathname }) {
  const ctx = useWorkflow()
  const crumbs = []
  const match = pathname.match(/^\/companies\/(\d+)(?:\/([^/]+))?/)

  if (match) {
    const [, id, segment] = match
    const base = `/companies/${id}`
    if (isAdmin) crumbs.push({ label: 'Companies', to: '/companies' })
    crumbs.push({ label: ctx?.company?.name || 'Company', to: isAdmin ? base : '/client' })
    const found = segment ? moduleForPath(segment) : null
    if (found) {
      crumbs.push({ label: `Step ${found.step.number} · ${found.step.title}`, to: `${base}/${stepEntry(found.step).path}` })
      if (found.step.modules.length > 1) crumbs.push({ label: found.module.label })
    } else if (segment === 'subscription') {
      crumbs.push({ label: 'Plan & usage' })
    } else if (!segment && isAdmin) {
      crumbs.push({ label: 'Overview' })
    }
  } else {
    const key = Object.keys(GLOBAL_TITLES).find((path) => pathname === path || pathname.startsWith(`${path}/`))
    const entry = key ? GLOBAL_TITLES[key] : null
    if (entry?.group) crumbs.push({ label: entry.group })
    if (entry) crumbs.push({ label: entry.label })
  }

  if (crumbs.length === 0) return <div className="crumbs" />
  return (
    <nav className="crumbs" aria-label="Breadcrumb">
      <ol>
        {crumbs.map((crumb, index) => {
          const last = index === crumbs.length - 1
          return (
            <li key={`${crumb.label}-${index}`}>
              {crumb.to && !last ? <Link to={crumb.to}>{crumb.label}</Link> : <span aria-current={last ? 'page' : undefined}>{crumb.label}</span>}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
