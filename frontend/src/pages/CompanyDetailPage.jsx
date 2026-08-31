import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import {
  addCompanyClient,
  getCompany,
  listCompanyClients,
  removeCompanyClient,
  setCompanyStatus,
  updateCompany,
  updateCompanyClient,
} from '../api/companies'
import { listCalendarItems } from '../api/contentCalendar'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import Modal from '../components/Modal'
import TagsInput from '../components/TagsInput'

const FIELD_LABELS = {
  name: 'Company name',
  industry: 'Industry',
  description: 'Description',
  contact_email: 'Contact email',
  contact_phone: 'Contact phone',
  address: 'Address',
  target_market: 'Target market',
  target_audience: 'Target audience',
  usp: 'USP',
  client: 'At least one client assigned',
}

const EMPTY_INFO_FORM = {
  name: '', industry: '', description: '', website: '',
  contact_email: '', contact_phone: '', address: '',
  target_market: '', target_audience: '', usp: '',
  products: [], services: [], competitors: [],
}

const EMPTY_CLIENT_FORM = {
  email: '', first_name: '', last_name: '', phone_number: '', designation: '', is_primary_contact: false,
}

export default function CompanyDetailPage() {
  const { id } = useParams()
  const { isAdmin } = useAuth()

  const [company, setCompany] = useState(null)
  const [clients, setClients] = useState([])
  const [calendarCount, setCalendarCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [editingInfo, setEditingInfo] = useState(false)
  const [infoForm, setInfoForm] = useState(EMPTY_INFO_FORM)
  const [infoError, setInfoError] = useState('')
  const [savingInfo, setSavingInfo] = useState(false)
  const [statusBusy, setStatusBusy] = useState(false)

  const [showAddClient, setShowAddClient] = useState(false)
  const [clientForm, setClientForm] = useState(EMPTY_CLIENT_FORM)
  const [clientError, setClientError] = useState('')
  const [addingClient, setAddingClient] = useState(false)
  const [newClientPassword, setNewClientPassword] = useState(null)

  const [editingClient, setEditingClient] = useState(null)
  const [removingClientId, setRemovingClientId] = useState(null)

  const load = useCallback(async () => {
    if (!isAdmin) {
      // This page is an admin management console (company/client CRUD) - a client
      // who lands here (stale link, browser history) gets redirected below rather
      // than this page firing admin-only requests (listCompanyClients) on their behalf.
      setLoading(false)
      return
    }
    setLoading(true)
    setLoadError('')
    try {
      const [companyData, clientsData, calendarData] = await Promise.all([
        getCompany(id),
        listCompanyClients(id),
        listCalendarItems(id),
      ])
      setCompany(companyData)
      setClients(clientsData.results)
      setCalendarCount(calendarData.count)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load this company.'))
    } finally {
      setLoading(false)
    }
  }, [id, isAdmin])

  useEffect(() => {
    load()
  }, [load])

  function startEditingInfo() {
    setInfoForm({
      name: company.name,
      industry: company.industry,
      description: company.description,
      website: company.website,
      contact_email: company.contact_email,
      contact_phone: company.contact_phone,
      address: company.address,
      target_market: company.target_market,
      target_audience: company.target_audience,
      usp: company.usp,
      products: company.products,
      services: company.services,
      competitors: company.competitors,
    })
    setInfoError('')
    setEditingInfo(true)
  }

  function updateInfoField(field, value) {
    setInfoForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSaveInfo(event) {
    event.preventDefault()
    setSavingInfo(true)
    setInfoError('')
    try {
      await updateCompany(id, infoForm)
      const fresh = await getCompany(id)
      setCompany(fresh)
      setEditingInfo(false)
    } catch (err) {
      setInfoError(extractErrorMessage(err, 'Could not save changes.'))
    } finally {
      setSavingInfo(false)
    }
  }

  async function handleToggleStatus() {
    setStatusBusy(true)
    try {
      const action = company.status === 'active' ? 'deactivate' : 'activate'
      const updated = await setCompanyStatus(id, action)
      setCompany(updated)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not update company status.'))
    } finally {
      setStatusBusy(false)
    }
  }

  function updateClientField(field, value) {
    setClientForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleAddClient(event) {
    event.preventDefault()
    setAddingClient(true)
    setClientError('')
    try {
      const created = await addCompanyClient(id, clientForm)
      setClients((prev) => [created, ...prev])
      setCompany((prev) => ({ ...prev, client_count: prev.client_count + 1 }))
      setClientForm(EMPTY_CLIENT_FORM)
      setShowAddClient(false)
      if (created.generated_password) {
        setNewClientPassword({ email: created.user.email, password: created.generated_password })
      }
    } catch (err) {
      setClientError(extractErrorMessage(err, 'Could not add this client.'))
    } finally {
      setAddingClient(false)
    }
  }

  async function handleSaveClientEdit(event) {
    event.preventDefault()
    try {
      const updated = await updateCompanyClient(id, editingClient.id, {
        designation: editingClient.designation,
        is_primary_contact: editingClient.is_primary_contact,
      })
      setClients((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
      setEditingClient(null)
    } catch (err) {
      setInfoError(extractErrorMessage(err, 'Could not update client.'))
    }
  }

  async function handleRemoveClient(clientId) {
    setRemovingClientId(clientId)
    try {
      await removeCompanyClient(id, clientId)
      setClients((prev) => prev.filter((c) => c.id !== clientId))
      setCompany((prev) => ({ ...prev, client_count: Math.max(0, prev.client_count - 1) }))
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not remove this client.'))
    } finally {
      setRemovingClientId(null)
    }
  }

  if (!isAdmin) return <Navigate to="/client" replace />
  if (loading) return <div className="page-loading">Loading…</div>
  if (loadError && !company) return <div className="alert alert-error">{loadError}</div>
  if (!company) return null

  const missingLabels = company.onboarding.missing_fields.map((field) => FIELD_LABELS[field] || field)

  return (
    <div>
      <Link to="/companies" className="back-link">
        ← Back to companies
      </Link>

      <div className="page-header">
        <div>
          <h1>{company.name}</h1>
          <div className="page-subtitle-row">
            <span className={`badge badge-${company.status}`}>{company.status}</span>
            <span className="page-subtitle">{company.industry || 'No industry set'}</span>
          </div>
        </div>
        <button type="button" className="btn btn-ghost" onClick={handleToggleStatus} disabled={statusBusy}>
          {company.status === 'active' ? 'Deactivate' : 'Activate'} company
        </button>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      <div className="detail-grid">
        <div className="card">
          <div className="card-header">
            <h2>Onboarding</h2>
            <span className="progress-label">{company.onboarding.completion_percentage}%</span>
          </div>
          <div className="progress">
            <div className="progress-bar" style={{ width: `${company.onboarding.completion_percentage}%` }} />
          </div>
          {company.onboarding.is_complete ? (
            <p className="onboarding-complete">✓ Onboarding complete</p>
          ) : (
            <ul className="checklist">
              {missingLabels.map((label) => (
                <li key={label}>{label}</li>
              ))}
            </ul>
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <h2>Business information</h2>
            {!editingInfo && (
              <button type="button" className="btn btn-ghost" onClick={startEditingInfo}>
                Edit
              </button>
            )}
          </div>

          {editingInfo ? (
            <form onSubmit={handleSaveInfo}>
              {infoError && <div className="alert alert-error">{infoError}</div>}
              <div className="field-row">
                <label className="field">
                  <span>Company name *</span>
                  <input value={infoForm.name} onChange={(e) => updateInfoField('name', e.target.value)} required />
                </label>
                <label className="field">
                  <span>Industry</span>
                  <input value={infoForm.industry} onChange={(e) => updateInfoField('industry', e.target.value)} />
                </label>
              </div>
              <label className="field">
                <span>Description</span>
                <textarea rows={3} value={infoForm.description} onChange={(e) => updateInfoField('description', e.target.value)} />
              </label>
              <label className="field">
                <span>Website</span>
                <input value={infoForm.website} onChange={(e) => updateInfoField('website', e.target.value)} />
              </label>
              <div className="field-row">
                <label className="field">
                  <span>Contact email</span>
                  <input type="email" value={infoForm.contact_email} onChange={(e) => updateInfoField('contact_email', e.target.value)} />
                </label>
                <label className="field">
                  <span>Contact phone</span>
                  <input value={infoForm.contact_phone} onChange={(e) => updateInfoField('contact_phone', e.target.value)} />
                </label>
              </div>
              <label className="field">
                <span>Address</span>
                <textarea rows={2} value={infoForm.address} onChange={(e) => updateInfoField('address', e.target.value)} />
              </label>
              <div className="field-row">
                <label className="field">
                  <span>Target market</span>
                  <textarea rows={2} value={infoForm.target_market} onChange={(e) => updateInfoField('target_market', e.target.value)} />
                </label>
                <label className="field">
                  <span>Target audience</span>
                  <textarea rows={2} value={infoForm.target_audience} onChange={(e) => updateInfoField('target_audience', e.target.value)} />
                </label>
              </div>
              <label className="field">
                <span>USP</span>
                <textarea rows={2} value={infoForm.usp} onChange={(e) => updateInfoField('usp', e.target.value)} />
              </label>
              <label className="field">
                <span>Products</span>
                <TagsInput value={infoForm.products} onChange={(v) => updateInfoField('products', v)} placeholder="Type a product, press Enter" />
              </label>
              <label className="field">
                <span>Services</span>
                <TagsInput value={infoForm.services} onChange={(v) => updateInfoField('services', v)} placeholder="Type a service, press Enter" />
              </label>
              <label className="field">
                <span>Competitors</span>
                <TagsInput value={infoForm.competitors} onChange={(v) => updateInfoField('competitors', v)} placeholder="Type a competitor, press Enter" />
              </label>

              <div className="modal-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setEditingInfo(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={savingInfo}>
                  {savingInfo ? 'Saving…' : 'Save changes'}
                </button>
              </div>
            </form>
          ) : (
            <dl className="detail-list">
              <InfoRow label="Description" value={company.description} />
              <InfoRow label="Website" value={company.website} />
              <InfoRow label="Contact email" value={company.contact_email} />
              <InfoRow label="Contact phone" value={company.contact_phone} />
              <InfoRow label="Address" value={company.address} />
              <InfoRow label="Target market" value={company.target_market} />
              <InfoRow label="Target audience" value={company.target_audience} />
              <InfoRow label="USP" value={company.usp} />
              <InfoRow label="Products" value={company.products} />
              <InfoRow label="Services" value={company.services} />
              <InfoRow label="Competitors" value={company.competitors} />
            </dl>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2>Brand management</h2>
          <Link to={`/companies/${id}/brand`} className="btn btn-primary">
            Open brand
          </Link>
        </div>
        <p className="page-subtitle">Logo, brand colors, guidelines, marketing information and brand assets.</p>
      </div>

      {isAdmin && (
        <div className="card">
          <div className="card-header">
            <h2>AI content strategy</h2>
            <Link to={`/companies/${id}/ai-strategy`} className="btn btn-primary">
              Open AI strategy
            </Link>
          </div>
          <p className="page-subtitle">Brand context, content ideas, and platform/audience/campaign strategy.</p>
        </div>
      )}

      {isAdmin && (
        <div className="card">
          <div className="card-header">
            <h2>AI creative generation</h2>
            <Link to={`/companies/${id}/creative-generation`} className="btn btn-primary">
              Open creative generation
            </Link>
          </div>
          <p className="page-subtitle">Generate brand-aware image + copy variations for social creatives.</p>
        </div>
      )}

      {isAdmin && (
        <div className="card">
          <div className="card-header">
            <h2>AI video generation</h2>
            <Link to={`/companies/${id}/video-generation`} className="btn btn-primary">
              Open video generation
            </Link>
          </div>
          <p className="page-subtitle">Generate scripted, scene-by-scene videos with voice-over and subtitles.</p>
        </div>
      )}

      {isAdmin && (
        <div className="card">
          <div className="card-header">
            <h2>Social media accounts</h2>
            <Link to={`/companies/${id}/social-accounts`} className="btn btn-primary">
              Open social accounts
            </Link>
          </div>
          <p className="page-subtitle">Connect Instagram, Facebook and LinkedIn accounts for publishing.</p>
        </div>
      )}

      {isAdmin && (
        <div className="card">
          <div className="card-header">
            <h2>Media library</h2>
            <Link to={`/companies/${id}/media-library`} className="btn btn-primary">
              Open media library
            </Link>
          </div>
          <p className="page-subtitle">Browse brand assets, generated creatives and videos in one place.</p>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <h2>Content calendar</h2>
          <Link to={`/companies/${id}/calendar`} className="btn btn-primary">
            Open calendar
          </Link>
        </div>
        <p className="page-subtitle">
          {calendarCount} item{calendarCount === 1 ? '' : 's'} scheduled for this company.
        </p>
      </div>

      <div className="card">
        <div className="card-header">
          <h2>Clients ({clients.length})</h2>
          <button type="button" className="btn btn-primary" onClick={() => setShowAddClient(true)}>
            + Add client
          </button>
        </div>

        {clients.length === 0 ? (
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
                  <th>Primary</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {clients.map((client) => (
                  <tr key={client.id}>
                    <td>{client.user.full_name}</td>
                    <td>{client.user.email}</td>
                    <td>{client.designation || '—'}</td>
                    <td>{client.is_primary_contact ? '★' : ''}</td>
                    <td className="table-actions">
                      <button type="button" className="btn-link" onClick={() => setEditingClient(client)}>
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn-link btn-link-danger"
                        disabled={removingClientId === client.id}
                        onClick={() => handleRemoveClient(client.id)}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showAddClient && (
        <Modal title="Add client" onClose={() => setShowAddClient(false)}>
          <form onSubmit={handleAddClient}>
            {clientError && <div className="alert alert-error">{clientError}</div>}
            <p className="modal-hint">Creates a new client login and assigns it to this company.</p>
            <label className="field">
              <span>Email *</span>
              <input type="email" value={clientForm.email} onChange={(e) => updateClientField('email', e.target.value)} required autoFocus />
            </label>
            <div className="field-row">
              <label className="field">
                <span>First name</span>
                <input value={clientForm.first_name} onChange={(e) => updateClientField('first_name', e.target.value)} />
              </label>
              <label className="field">
                <span>Last name</span>
                <input value={clientForm.last_name} onChange={(e) => updateClientField('last_name', e.target.value)} />
              </label>
            </div>
            <label className="field">
              <span>Phone number</span>
              <input value={clientForm.phone_number} onChange={(e) => updateClientField('phone_number', e.target.value)} />
            </label>
            <label className="field">
              <span>Designation</span>
              <input value={clientForm.designation} onChange={(e) => updateClientField('designation', e.target.value)} placeholder="e.g. Marketing Manager" />
            </label>
            <label className="field-checkbox">
              <input
                type="checkbox"
                checked={clientForm.is_primary_contact}
                onChange={(e) => updateClientField('is_primary_contact', e.target.checked)}
              />
              <span>Primary contact</span>
            </label>

            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setShowAddClient(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={addingClient}>
                {addingClient ? 'Adding…' : 'Add client'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {editingClient && (
        <Modal title="Edit client" onClose={() => setEditingClient(null)}>
          <form onSubmit={handleSaveClientEdit}>
            <p className="modal-hint">{editingClient.user.email}</p>
            <label className="field">
              <span>Designation</span>
              <input
                value={editingClient.designation}
                onChange={(e) => setEditingClient((prev) => ({ ...prev, designation: e.target.value }))}
              />
            </label>
            <label className="field-checkbox">
              <input
                type="checkbox"
                checked={editingClient.is_primary_contact}
                onChange={(e) => setEditingClient((prev) => ({ ...prev, is_primary_contact: e.target.checked }))}
              />
              <span>Primary contact</span>
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setEditingClient(null)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary">
                Save
              </button>
            </div>
          </form>
        </Modal>
      )}

      {newClientPassword && (
        <Modal title="Client created" onClose={() => setNewClientPassword(null)}>
          <p>
            Share these credentials with <strong>{newClientPassword.email}</strong> securely — the password won't be shown again.
          </p>
          <div className="credential-box">
            <div>
              <span className="credential-label">Email</span>
              <code>{newClientPassword.email}</code>
            </div>
            <div>
              <span className="credential-label">Temporary password</span>
              <code>{newClientPassword.password}</code>
            </div>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-primary" onClick={() => setNewClientPassword(null)}>
              Done
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}

function InfoRow({ label, value }) {
  const isEmpty = Array.isArray(value) ? value.length === 0 : !value
  return (
    <div className="detail-row">
      <dt>{label}</dt>
      <dd>
        {isEmpty ? (
          <span className="muted">Not set</span>
        ) : Array.isArray(value) ? (
          <div className="tag-list">
            {value.map((item) => (
              <span key={item} className="tag-chip tag-chip-static">
                {item}
              </span>
            ))}
          </div>
        ) : (
          value
        )}
      </dd>
    </div>
  )
}
