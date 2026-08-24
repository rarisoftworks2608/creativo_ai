import { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { createAdmin, listTeam, setAdminActive } from '../api/team'
import { extractErrorMessage } from '../api/client'
import Modal from '../components/Modal'

const EMPTY_FORM = { email: '', first_name: '', last_name: '', phone_number: '' }

function formatLastLogin(value) {
  if (!value) return 'Never signed in'
  return new Date(value).toLocaleString()
}

export default function TeamPage() {
  const { user: currentUser, isAdmin } = useAuth()

  const [members, setMembers] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [formError, setFormError] = useState('')
  const [creating, setCreating] = useState(false)

  const [newAdminCredentials, setNewAdminCredentials] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const data = await listTeam()
      setMembers(data.results)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load the team.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isAdmin) load()
  }, [isAdmin, load])

  if (!isAdmin) return <Navigate to="/companies" replace />

  function updateForm(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleCreate(event) {
    event.preventDefault()
    setFormError('')
    setCreating(true)
    try {
      const created = await createAdmin(form)
      setMembers((prev) => [created, ...prev])
      setForm(EMPTY_FORM)
      setShowAdd(false)
      if (created.generated_password) {
        setNewAdminCredentials({ email: created.email, password: created.generated_password })
      }
    } catch (err) {
      setFormError(extractErrorMessage(err, 'Could not add this admin.'))
    } finally {
      setCreating(false)
    }
  }

  async function handleToggleActive(member) {
    try {
      const updated = await setAdminActive(member.id, !member.is_active)
      setMembers((prev) => prev.map((m) => (m.id === updated.id ? updated : m)))
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not update this admin.'))
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Team</h1>
          <p className="page-subtitle">Admins who can manage every company on the platform.</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowAdd(true)}>
          + Add admin
        </button>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      <div className="card">
        {loading ? (
          <div className="empty-state">Loading…</div>
        ) : members.length === 0 ? (
          <div className="empty-state">
            <p>No admins yet.</p>
            <button type="button" className="btn btn-primary" onClick={() => setShowAdd(true)}>
              Add your first teammate
            </button>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Status</th>
                  <th>Last login</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {members.map((member) => (
                  <tr key={member.id}>
                    <td>{member.full_name}</td>
                    <td>{member.email}</td>
                    <td>
                      <span className={`badge badge-${member.is_active ? 'active' : 'inactive'}`}>
                        {member.is_active ? 'Active' : 'Deactivated'}
                      </span>
                    </td>
                    <td>{formatLastLogin(member.last_login)}</td>
                    <td>
                      {member.id !== currentUser?.id && (
                        <button
                          type="button"
                          className="btn-link btn-link-danger"
                          onClick={() => handleToggleActive(member)}
                        >
                          {member.is_active ? 'Deactivate' : 'Reactivate'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showAdd && (
        <Modal title="Add admin" onClose={() => setShowAdd(false)}>
          <form onSubmit={handleCreate}>
            {formError && <div className="alert alert-error">{formError}</div>}

            <label className="field">
              <span>Email *</span>
              <input
                type="email"
                value={form.email}
                onChange={(e) => updateForm('email', e.target.value)}
                required
                autoFocus
              />
            </label>
            <div className="field-row">
              <label className="field">
                <span>First name</span>
                <input value={form.first_name} onChange={(e) => updateForm('first_name', e.target.value)} />
              </label>
              <label className="field">
                <span>Last name</span>
                <input value={form.last_name} onChange={(e) => updateForm('last_name', e.target.value)} />
              </label>
            </div>
            <label className="field">
              <span>Phone number</span>
              <input value={form.phone_number} onChange={(e) => updateForm('phone_number', e.target.value)} />
            </label>
            <p className="field-hint">
              A temporary password is generated automatically and emailed to them along with a login link.
            </p>

            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setShowAdd(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={creating}>
                {creating ? 'Adding…' : 'Add admin'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {newAdminCredentials && (
        <Modal title="Admin added" onClose={() => setNewAdminCredentials(null)}>
          <p>
            Share these credentials with <strong>{newAdminCredentials.email}</strong> securely — the password won't
            be shown again.
          </p>
          <div className="credential-box">
            <div>
              <span className="credential-label">Email</span>
              <code>{newAdminCredentials.email}</code>
            </div>
            <div>
              <span className="credential-label">Temporary password</span>
              <code>{newAdminCredentials.password}</code>
            </div>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-primary" onClick={() => setNewAdminCredentials(null)}>
              Done
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
