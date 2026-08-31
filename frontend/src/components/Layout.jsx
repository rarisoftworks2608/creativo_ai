import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import NotificationBell from './NotificationBell'
import ChangePasswordModal from './ChangePasswordModal'

export default function Layout() {
  const { user, isAdmin, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [navOpen, setNavOpen] = useState(false)
  const [showChangePassword, setShowChangePassword] = useState(false)

  useEffect(() => {
    setNavOpen(false)
  }, [location.pathname])

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="shell">
      <aside className={`sidebar ${navOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <span className="brand-mark">AI</span>
          <span>Marketing OS</span>
        </div>
        <nav className="sidebar-nav">
          {isAdmin ? (
            <>
              <NavLink to="/dashboard" className={({ isActive }) => (isActive ? 'active' : '')} onClick={() => setNavOpen(false)}>
                <span className="nav-icon" aria-hidden="true">
                  <svg viewBox="0 0 20 20" fill="none">
                    <path
                      d="M3 17V8.5L10 3l7 5.5V17a1 1 0 0 1-1 1h-3.5a.5.5 0 0 1-.5-.5V13a2 2 0 0 0-4 0v4.5a.5.5 0 0 1-.5.5H4a1 1 0 0 1-1-1Z"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
                Dashboard
              </NavLink>
              <NavLink to="/companies" className={({ isActive }) => (isActive ? 'active' : '')} onClick={() => setNavOpen(false)}>
                <span className="nav-icon" aria-hidden="true">
                  <svg viewBox="0 0 20 20" fill="none">
                    <rect x="3" y="3.5" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
                    <rect x="11" y="3.5" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
                    <rect x="3" y="11.5" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
                    <rect x="11" y="11.5" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
                  </svg>
                </span>
                Companies
              </NavLink>
            </>
          ) : (
            <NavLink to="/client" className={({ isActive }) => (isActive ? 'active' : '')} onClick={() => setNavOpen(false)}>
              <span className="nav-icon" aria-hidden="true">
                <svg viewBox="0 0 20 20" fill="none">
                  <path
                    d="M3 17V8.5L10 3l7 5.5V17a1 1 0 0 1-1 1h-3.5a.5.5 0 0 1-.5-.5V13a2 2 0 0 0-4 0v4.5a.5.5 0 0 1-.5.5H4a1 1 0 0 1-1-1Z"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
              Dashboard
            </NavLink>
          )}
          {isAdmin && (
            <NavLink to="/access" className={({ isActive }) => (isActive ? 'active' : '')} onClick={() => setNavOpen(false)}>
              <span className="nav-icon" aria-hidden="true">
                <svg viewBox="0 0 20 20" fill="none">
                  <rect x="3.5" y="8.5" width="13" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
                  <path d="M6.5 8.5V6a3.5 3.5 0 0 1 7 0v2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </span>
              Access
            </NavLink>
          )}
          {isAdmin && (
            <NavLink to="/team" className={({ isActive }) => (isActive ? 'active' : '')} onClick={() => setNavOpen(false)}>
              <span className="nav-icon" aria-hidden="true">
                <svg viewBox="0 0 20 20" fill="none">
                  <circle cx="7" cy="6.5" r="2.75" stroke="currentColor" strokeWidth="1.5" />
                  <path
                    d="M2.5 16.5c0-2.9 2.24-4.75 4.5-4.75s4.5 1.85 4.5 4.75"
                    stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"
                  />
                  <circle cx="14" cy="6.5" r="2.25" stroke="currentColor" strokeWidth="1.5" />
                  <path
                    d="M12.5 12c1.9.35 3.5 1.9 3.5 4.5"
                    stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"
                  />
                </svg>
              </span>
              Team
            </NavLink>
          )}
        </nav>
      </aside>

      {navOpen && <div className="sidebar-backdrop" onClick={() => setNavOpen(false)} />}

      <div className="shell-main">
        <header className="topbar">
          <button
            type="button"
            className="hamburger-btn"
            onClick={() => setNavOpen((prev) => !prev)}
            aria-label="Toggle navigation"
          >
            <svg viewBox="0 0 20 20" fill="none">
              <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>

          <div className="topbar-user">
            <NotificationBell />
            <div className="user-badge">
              <span className="user-avatar">{user?.email?.[0]?.toUpperCase() ?? '?'}</span>
              <div className="user-text">
                <div className="user-name">{user?.full_name || user?.email}</div>
                <div className="user-role">{user?.role}</div>
              </div>
            </div>
            <button type="button" className="btn btn-ghost" onClick={() => setShowChangePassword(true)}>
              Change password
            </button>
            <button type="button" className="btn btn-ghost" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </header>

        <main className="content">
          <Outlet />
        </main>
      </div>

      {showChangePassword && <ChangePasswordModal onClose={() => setShowChangePassword(false)} />}
    </div>
  )
}
