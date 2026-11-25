import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { createCompany, listCompanies } from '../api/companies'
import { extractErrorMessage } from '../api/client'
import Modal from '../components/Modal'

const EMPTY_FORM = { name: '', industry: '', description: '', website: '', contact_email: '', contact_phone: '' }

export default function CompaniesListPage() {
  const navigate = useNavigate()

  const [companies, setCompanies] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')

  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [formError, setFormError] = useState('')
  const [creating, setCreating] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const data = await listCompanies({ search, status })
      setCompanies(data.results)
      setCount(data.count)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load companies.'))
    } finally {
      setLoading(false)
    }
  }, [search, status])

  useEffect(() => {
    const timeout = setTimeout(load, 300)
    return () => clearTimeout(timeout)
  }, [load])

  function updateForm(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleCreate(event) {
    event.preventDefault()
    setFormError('')
    setCreating(true)
    try {
      const company = await createCompany(form)
      setShowCreate(false)
      setForm(EMPTY_FORM)
      navigate(`/companies/${company.id}`)
    } catch (err) {
      setFormError(extractErrorMessage(err, 'Could not create company.'))
    } finally {
      setCreating(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Companies</h1>
          <p className="page-subtitle">
            {count} {count === 1 ? 'company' : 'companies'} · open one to work through its content workflow
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
          + Add company
        </button>
      </div>

      <div className="toolbar adm-toolbar">
        <input
          type="search"
          aria-label="Search companies"
          placeholder="Search companies…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="search-input"
        />
        <select className="status-select" aria-label="Filter by status" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      <div className="card">
        {loading ? (
          <div className="empty-state">Loading…</div>
        ) : companies.length === 0 ? (
          <div className="empty-state">
            <p>No companies yet.</p>
            <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
              Create your first company
            </button>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="table table-stack adm-company-table">
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Status</th>
                  <th>Clients</th>
                  <th>Setup</th>
                  <th>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {companies.map((company) => {
                  const setup = company.onboarding?.completion_percentage ?? 0
                  return (
                    <tr key={company.id} className="table-row-link" onClick={() => navigate(`/companies/${company.id}`)}>
                      <td data-label="Company">
                        <span className="adm-cell-company">
                          <span className="adm-company-avatar" aria-hidden="true">
                            {company.name.charAt(0).toUpperCase()}
                          </span>
                          <span className="adm-company-main">
                            <Link
                              to={`/companies/${company.id}`}
                              className="adm-company-name"
                              onClick={(event) => event.stopPropagation()}
                            >
                              {company.name}
                            </Link>
                            <span className="adm-company-meta">{company.industry || 'No industry set'}</span>
                          </span>
                        </span>
                      </td>
                      <td data-label="Status">
                        <span className={`badge badge-${company.status}`}>{company.status}</span>
                      </td>
                      <td data-label="Clients">{company.client_count}</td>
                      <td data-label="Setup">
                        <span className="adm-company-setup">
                          <span className="adm-setup-bar">
                            <span style={{ width: `${setup}%` }} />
                          </span>
                          <span className="adm-setup-label">{setup}%</span>
                        </span>
                      </td>
                      <td className="table-actions">
                        <Link
                          to={`/companies/${company.id}`}
                          className="btn btn-ghost btn-sm"
                          onClick={(event) => event.stopPropagation()}
                        >
                          Open workspace
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showCreate && (
        <Modal title="Add company" onClose={() => setShowCreate(false)}>
          <form onSubmit={handleCreate}>
            {formError && <div className="alert alert-error">{formError}</div>}

            <label className="field">
              <span>Company name *</span>
              <input value={form.name} onChange={(e) => updateForm('name', e.target.value)} required autoFocus />
            </label>
            <label className="field">
              <span>Industry</span>
              <input value={form.industry} onChange={(e) => updateForm('industry', e.target.value)} />
            </label>
            <label className="field">
              <span>Description</span>
              <textarea rows={3} value={form.description} onChange={(e) => updateForm('description', e.target.value)} />
            </label>
            <div className="field-row">
              <label className="field">
                <span>Contact email</span>
                <input type="email" value={form.contact_email} onChange={(e) => updateForm('contact_email', e.target.value)} />
              </label>
              <label className="field">
                <span>Contact phone</span>
                <input value={form.contact_phone} onChange={(e) => updateForm('contact_phone', e.target.value)} />
              </label>
            </div>
            <label className="field">
              <span>Website</span>
              <input value={form.website} onChange={(e) => updateForm('website', e.target.value)} placeholder="https://" />
            </label>

            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={creating}>
                {creating ? 'Creating…' : 'Create company'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
