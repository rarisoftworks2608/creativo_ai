import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { listCompanies, listCompanyClients } from '../api/companies'
import { setUserActive } from '../api/team'
import { extractErrorMessage } from '../api/client'

export default function AccessControlPage() {
  const { isAdmin } = useAuth()

  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [busyClientId, setBusyClientId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const companiesData = await listCompanies()
      const companies = companiesData.results
      const clientLists = await Promise.all(companies.map((company) => listCompanyClients(company.id)))
      setGroups(companies.map((company, index) => ({ company, clients: clientLists[index].results })))
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load access information.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isAdmin) load()
  }, [isAdmin, load])

  if (!isAdmin) return <Navigate to="/companies" replace />

  async function handleToggleActive(companyId, client) {
    setBusyClientId(client.id)
    try {
      const updatedUser = await setUserActive(client.user.id, !client.user.is_active)
      setGroups((prev) =>
        prev.map((group) =>
          group.company.id !== companyId
            ? group
            : { ...group, clients: group.clients.map((c) => (c.id === client.id ? { ...c, user: updatedUser } : c)) },
        ),
      )
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not update this client.'))
    } finally {
      setBusyClientId(null)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Access Control</h1>
          <p className="page-subtitle">Every client login, grouped by company — activate or deactivate access.</p>
        </div>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      {loading ? (
        <div className="empty-state">Loading…</div>
      ) : groups.length === 0 ? (
        <div className="empty-state">
          <p>No companies yet.</p>
        </div>
      ) : (
        groups.map((group) => (
          <div className="card" key={group.company.id}>
            <div className="card-header">
              <h2>
                <Link to={`/companies/${group.company.id}`}>{group.company.name}</Link>
              </h2>
              <span className={`badge badge-${group.company.status}`}>{group.company.status}</span>
            </div>

            {group.clients.length === 0 ? (
              <div className="empty-state">
                <p>No clients assigned yet.</p>
              </div>
            ) : (
              <div className="table-wrapper">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Designation</th>
                      <th>Status</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {group.clients.map((client) => (
                      <tr key={client.id}>
                        <td>{client.user.full_name}</td>
                        <td>{client.user.email}</td>
                        <td>{client.designation || '—'}</td>
                        <td>
                          <span className={`badge badge-${client.user.is_active ? 'active' : 'inactive'}`}>
                            {client.user.is_active ? 'Active' : 'Deactivated'}
                          </span>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="btn-link btn-link-danger"
                            disabled={busyClientId === client.id}
                            onClick={() => handleToggleActive(group.company.id, client)}
                          >
                            {client.user.is_active ? 'Deactivate' : 'Reactivate'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  )
}
