import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import NotificationBell from './NotificationBell'

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [navOpen, setNavOpen] = useState(false)

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
          <NavLink to="/companies" className={({ isActive }) => (isActive ? 'active' : '')} onClick={() => setNavOpen(false)}>
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
            Companies
          </NavLink>
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
            <button type="button" className="btn btn-ghost" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </header>

        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
