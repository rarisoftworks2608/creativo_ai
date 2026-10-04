import { Suspense, useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getApprovalStats } from '../api/approvals'
import { getMyCompany } from '../api/companies'
import NotificationBell from './NotificationBell'
import ChangePasswordModal from './ChangePasswordModal'
import ICONS from './DashboardIcons'
import { visibleModules } from '../context/CompanyWorkspaceContext'

const ADMIN_NAV = [
  { items: [{ to: '/dashboard', label: 'Dashboard', icon: 'building' }] },
  {
    title: 'Workspace',
    items: [
      { to: '/companies', label: 'Companies', icon: 'building' },
      { to: '/approvals', label: 'Approvals', icon: 'check', badge: 'approvals' },
      { to: '/publishing', label: 'Publishing', icon: 'send' },
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
    title: 'Business',
    items: [
      { to: '/subscriptions', label: 'Subscriptions', icon: 'dollar' },
      { to: '/team', label: 'Team', icon: 'users' },
      { to: '/access', label: 'Access', icon: 'shield' },
    ],
  },
  {
    title: 'Automation',
    items: [
      { to: '/whatsapp', label: 'WhatsApp', icon: 'chat' },
      { to: '/prompt-templates', label: 'Prompt Library', icon: 'wand' },
      { to: '/music-library', label: 'Music Library', icon: 'music' },
    ],
  },
  {
    title: 'System',
    items: [
      { to: '/jobs', label: 'Jobs', icon: 'clock' },
      { to: '/activity-log', label: 'Activity Log', icon: 'file' },
      { to: '/system-health', label: 'System Health', icon: 'alert' },
      { to: '/admin-settings', label: 'Admin Settings', icon: 'sparkle' },
    ],
  },
]

const CLIENT_ICONS = {
  approvals: 'check', calendar: 'calendar', 'creative-generation': 'wand', 'video-generation': 'video',
  publishing: 'send', analytics: 'chart', reports: 'file', brand: 'image', 'ai-strategy': 'sparkle', subscription: 'dollar',
}
const CLIENT_ORDER = ['approvals', 'calendar', 'creative-generation', 'video-generation', 'publishing', 'analytics', 'reports', 'brand', 'ai-strategy', 'subscription']

function NavItem({ item, badgeCount }) {
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

export default function Layout() {
  const { user, isAdmin, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [navOpen, setNavOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [showChangePassword, setShowChangePassword] = useState(false)
  const [pendingApprovals, setPendingApprovals] = useState(0)
  const [clientCompany, setClientCompany] = useState(null)
  const menuRef = useRef(null)

  useEffect(() => {
    setNavOpen(false)
    setMenuOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!isAdmin) return undefined
    let cancelled = false
    const refresh = () =>
      getApprovalStats()
        .then((stats) => {
          if (!cancelled) setPendingApprovals(stats.pending_approval)
        })
        .catch(() => {})
    refresh()
    const timer = setInterval(refresh, 60000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [isAdmin])

  useEffect(() => {
    if (isAdmin || !user) return
    getMyCompany().then(setClientCompany).catch(() => setClientCompany(null))
  }, [isAdmin, user])

  useEffect(() => {
    if (!menuOpen) return undefined
    function onPointerDown(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) setMenuOpen(false)
    }
    function onKeyDown(event) {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [menuOpen])

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  const clientItems = clientCompany
    ? visibleModules(false, clientCompany.page_permissions || [])
        .filter((module) => CLIENT_ORDER.includes(module.path))
        .sort((a, b) => CLIENT_ORDER.indexOf(a.path) - CLIENT_ORDER.indexOf(b.path))
        .map((module) => ({
          to: `/companies/${clientCompany.id}/${module.path}`,
          label: module.label,
          icon: CLIENT_ICONS[module.path] || 'sparkle',
        }))
    : []

  return (
    <div className="shell">
      <aside className={`sidebar ${navOpen ? 'open' : ''}`} aria-label="Main navigation">
        <div className="sidebar-brand">
          <span className="brand-mark">AI</span>
          <span>Creativo AI</span>
          <button type="button" className="sidebar-close" onClick={() => setNavOpen(false)} aria-label="Close navigation">
            ×
          </button>
        </div>
        <nav className="sidebar-nav">
          {isAdmin ? (
            ADMIN_NAV.map((group, index) => (
              <div className="nav-group" key={group.title || index}>
                {group.title && <div className="nav-group-title">{group.title}</div>}
                {group.items.map((item) => (
                  <NavItem key={item.to} item={item} badgeCount={item.badge === 'approvals' ? pendingApprovals : 0} />
                ))}
              </div>
            ))
          ) : (
            <>
              <div className="nav-group">
                <NavItem item={{ to: '/client', label: 'Dashboard', icon: 'building' }} />
              </div>
              {clientItems.length > 0 && (
                <div className="nav-group">
                  <div className="nav-group-title">{clientCompany?.name || 'My company'}</div>
                  {clientItems.map((item) => (
                    <NavItem key={item.to} item={item} />
                  ))}
                </div>
              )}
              <div className="nav-group">
                <div className="nav-group-title">Account</div>
                <NavItem item={{ to: '/settings', label: 'My account', icon: 'users' }} />
              </div>
            </>
          )}
        </nav>
      </aside>

      {navOpen && <div className="sidebar-backdrop" onClick={() => setNavOpen(false)} />}

      <div className="shell-main">
        <header className="topbar">
          <button type="button" className="hamburger-btn" onClick={() => setNavOpen((prev) => !prev)} aria-label="Open navigation">
            <svg viewBox="0 0 20 20" fill="none">
              <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>
          <Link to={isAdmin ? '/dashboard' : '/client'} className="topbar-brand">
            Creativo AI
          </Link>

          <div className="topbar-user">
            <NotificationBell />
            <div className="user-menu" ref={menuRef}>
              <button
                type="button"
                className="user-badge"
                onClick={() => setMenuOpen((prev) => !prev)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
              >
                <span className="user-avatar">{user?.email?.[0]?.toUpperCase() ?? '?'}</span>
                <span className="user-text">
                  <span className="user-name">{user?.full_name || user?.email}</span>
                  <span className="user-role">{user?.role}</span>
                </span>
                <span className="user-caret" aria-hidden="true">
                  ▾
                </span>
              </button>
              {menuOpen && (
                <div className="user-dropdown" role="menu">
                  <div className="user-dropdown-head">
                    <strong>{user?.full_name || user?.email}</strong>
                    <span>{user?.email}</span>
                  </div>
                  <Link to="/settings" role="menuitem" className="user-dropdown-item">
                    My account
                  </Link>
                  <button
                    type="button"
                    role="menuitem"
                    className="user-dropdown-item"
                    onClick={() => {
                      setMenuOpen(false)
                      setShowChangePassword(true)
                    }}
                  >
                    Change password
                  </button>
                  <button type="button" role="menuitem" className="user-dropdown-item user-dropdown-danger" onClick={handleLogout}>
                    Log out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="content">
          <Suspense fallback={<div className="page-loading">Loading…</div>}>
            <Outlet />
          </Suspense>
        </main>
      </div>

      {showChangePassword && <ChangePasswordModal onClose={() => setShowChangePassword(false)} />}
    </div>
  )
}
