import { Suspense, useEffect, useRef, useState } from 'react'
import { Link, Outlet, useLocation, useMatch, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getApprovalStats } from '../api/approvals'
import { getMyCompany } from '../api/companies'
import NotificationBell from './NotificationBell'
import ChangePasswordModal from './ChangePasswordModal'
import WorkflowProvider from './WorkflowProvider'
import { AdminNav, Breadcrumbs, WorkspaceNav } from './AppNavigation'

/**
 * App shell. The sidebar has two modes:
 *  - global (admin, outside a company): dashboard, companies and cross-company tools;
 *  - workspace (inside a company, and always for a client): a company switcher and the
 *    company's numbered content workflow, each step with its sub-sections nested below.
 * The top bar carries the breadcrumb, notifications and the account menu.
 */
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

  const companyMatch = useMatch('/companies/:id/*')
  const workflowCompanyId = isAdmin ? companyMatch?.params.id || null : clientCompany?.id || null
  const inWorkspace = Boolean(workflowCompanyId)

  return (
    <WorkflowProvider
      companyId={workflowCompanyId}
      isAdmin={isAdmin}
      permissions={isAdmin ? null : clientCompany?.page_permissions || []}
    >
      <div className="shell">
        <aside className={`sidebar ${navOpen ? 'open' : ''}`} aria-label="Main navigation">
          <div className="sidebar-brand">
            <Link to={isAdmin ? '/dashboard' : '/client'} className="sidebar-brand-link">
              <span className="brand-mark">C</span>
              <span>Creativo AI</span>
            </Link>
            <button type="button" className="sidebar-close" onClick={() => setNavOpen(false)} aria-label="Close navigation">
              ×
            </button>
          </div>
          <nav className="sidebar-nav">
            {inWorkspace ? (
              <WorkspaceNav isAdmin={isAdmin} pathname={location.pathname} />
            ) : (
              <AdminNav pathname={location.pathname} pendingApprovals={pendingApprovals} />
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
            <Breadcrumbs isAdmin={isAdmin} pathname={location.pathname} />

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
    </WorkflowProvider>
  )
}
