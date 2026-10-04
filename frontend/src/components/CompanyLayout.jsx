import { Suspense, useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useParams } from 'react-router-dom'
import { getCompany, getMyCompany } from '../api/companies'
import { useAuth } from '../context/AuthContext'
import { CompanyWorkspaceContext, visibleModules } from '../context/CompanyWorkspaceContext'

/**
 * Wraps every /companies/:id/... page with the company's module navigation, so moving
 * between Brand, Calendar, Approvals, Publishing, Analytics ... is one tap away on any
 * screen size, and a client only ever sees the modules they were granted.
 */
export default function CompanyLayout() {
  const { id } = useParams()
  const { isAdmin } = useAuth()
  const [company, setCompany] = useState(null)
  const [permissions, setPermissions] = useState([])

  useEffect(() => {
    let cancelled = false
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

  const modules = visibleModules(isAdmin, permissions)

  return (
    <CompanyWorkspaceContext.Provider value={{ company, permissions }}>
      <div className="company-workspace">
        <div className="company-nav-bar">
          <div className="company-nav-title">
            {isAdmin ? (
              <Link to="/companies" className="company-nav-back" aria-label="All companies">
                ←
              </Link>
            ) : null}
            <span className="company-nav-name">{company?.name || 'Company'}</span>
          </div>
          <nav className="company-nav" aria-label="Company modules">
            {modules.map((module) => (
              <NavLink
                key={module.path || 'overview'}
                to={module.path ? `/companies/${id}/${module.path}` : `/companies/${id}`}
                end={module.end}
                className={({ isActive }) => `company-nav-link ${isActive ? 'active' : ''}`}
              >
                {module.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <Suspense fallback={<div className="page-loading">Loading…</div>}>
          <Outlet />
        </Suspense>
      </div>
    </CompanyWorkspaceContext.Provider>
  )
}
