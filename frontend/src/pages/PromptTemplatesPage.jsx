import { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  activatePromptTemplate,
  createPromptTemplate,
  createPromptTemplateVersion,
  deactivatePromptTemplate,
  deletePromptTemplate,
  fetchPromptTemplateHistory,
  listPromptTemplates,
} from '../api/promptTemplates'
import { extractErrorMessage } from '../api/client'
import Modal from '../components/Modal'

const CATEGORIES = [
  { value: 'image', label: 'Image Prompts' },
  { value: 'caption', label: 'Caption Prompts' },
  { value: 'video', label: 'Video Prompts' },
  { value: 'hashtag', label: 'Hashtag Prompts' },
  { value: 'campaign', label: 'Campaign Prompts' },
]

const PLATFORMS = [
  { value: '', label: 'All platforms' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'facebook', label: 'Facebook' },
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'general', label: 'General' },
]

const CREATIVE_TYPES = [
  { value: '', label: 'All creative types' },
  { value: 'post', label: 'Post' },
  { value: 'carousel', label: 'Carousel' },
  { value: 'story', label: 'Story' },
  { value: 'promotional_creative', label: 'Promotional' },
  { value: 'festival_creative', label: 'Festival' },
  { value: 'product_creative', label: 'Product' },
  { value: 'educational_creative', label: 'Educational' },
  { value: 'event_creative', label: 'Event' },
  { value: 'announcement_creative', label: 'Announcement' },
  { value: 'testimonial_creative', label: 'Testimonial' },
]

const EMPTY_FORM = { slug: '', category: 'image', platform: '', creative_type: '', name: '', body: '' }

function scopeLabel(template) {
  const parts = []
  if (template.platform) parts.push(PLATFORMS.find((p) => p.value === template.platform)?.label || template.platform)
  if (template.creative_type) {
    parts.push(CREATIVE_TYPES.find((c) => c.value === template.creative_type)?.label || template.creative_type)
  }
  return parts.length ? parts.join(' · ') : 'All'
}

export default function PromptTemplatesPage() {
  const { isAdmin } = useAuth()

  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [category, setCategory] = useState('')

  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [formError, setFormError] = useState('')
  const [creating, setCreating] = useState(false)

  const [activeSlug, setActiveSlug] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const data = await listPromptTemplates(category ? { category } : {})
      setTemplates(data.results)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load prompt templates.'))
    } finally {
      setLoading(false)
    }
  }, [category])

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
      await createPromptTemplate(form)
      setShowCreate(false)
      setForm(EMPTY_FORM)
      load()
    } catch (err) {
      setFormError(extractErrorMessage(err, 'Could not create this template.'))
    } finally {
      setCreating(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>AI Prompt &amp; Template Library</h1>
          <p className="page-subtitle">Extra guidance injected into AI generation prompts, versioned and activated on demand.</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
          + New template
        </button>
      </div>

      <div className="toolbar">
        <select className="status-select" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      <div className="card">
        {loading ? (
          <div className="empty-state">Loading…</div>
        ) : templates.length === 0 ? (
          <div className="empty-state">
            <p>No prompt templates yet. Generations use the built-in defaults until you add one.</p>
            <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
              Create your first template
            </button>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Category</th>
                  <th>Scope</th>
                  <th>Version</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {templates.map((template) => (
                  <tr key={template.id} className="table-row-link" onClick={() => setActiveSlug(template.slug)}>
                    <td>{template.name}</td>
                    <td>{template.category_display}</td>
                    <td>{scopeLabel(template)}</td>
                    <td>v{template.version}</td>
                    <td>
                      <span className={`badge badge-${template.is_active ? 'active' : 'inactive'}`}>
                        {template.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      <button type="button" className="btn-link" onClick={() => setActiveSlug(template.slug)}>
                        Manage
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showCreate && (
        <Modal title="New prompt template" onClose={() => setShowCreate(false)} width={600}>
          <form onSubmit={handleCreate}>
            {formError && <div className="alert alert-error">{formError}</div>}
            <label className="field">
              <span>Slug (unique identifier for this template)</span>
              <input
                value={form.slug}
                onChange={(e) => updateForm('slug', e.target.value)}
                placeholder="e.g. luxury-real-estate-image"
                required
                autoFocus
              />
            </label>
            <label className="field">
              <span>Name</span>
              <input value={form.name} onChange={(e) => updateForm('name', e.target.value)} required />
            </label>
            <div className="field-row">
              <label className="field">
                <span>Category</span>
                <select value={form.category} onChange={(e) => updateForm('category', e.target.value)}>
                  {CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Platform (optional)</span>
                <select value={form.platform} onChange={(e) => updateForm('platform', e.target.value)}>
                  {PLATFORMS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="field">
              <span>Creative type (optional)</span>
              <select value={form.creative_type} onChange={(e) => updateForm('creative_type', e.target.value)}>
                {CREATIVE_TYPES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Guidance text</span>
              <textarea
                rows={6}
                value={form.body}
                onChange={(e) => updateForm('body', e.target.value)}
                placeholder="Extra instructions appended to the AI prompt, e.g. 'Always emphasize marble and gold accents.'"
                required
              />
            </label>
            <p className="field-hint">
              Leave platform/creative type blank to apply to everything in this category. This is created inactive —
              activate it afterward to make it live.
            </p>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={creating}>
                {creating ? 'Creating…' : 'Create template'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {activeSlug && (
        <TemplateHistoryModal
          slug={activeSlug}
          onClose={() => setActiveSlug(null)}
          onChanged={load}
        />
      )}
    </div>
  )
}

function TemplateHistoryModal({ slug, onClose, onChanged }) {
  const [versions, setVersions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editingBody, setEditingBody] = useState('')
  const [savingVersion, setSavingVersion] = useState(false)
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchPromptTemplateHistory(slug)
      setVersions(data.results)
      setEditingBody(data.results[0]?.body || '')
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load version history.'))
    } finally {
      setLoading(false)
    }
  }, [slug])

  useEffect(() => {
    load()
  }, [load])

  const latest = versions[0]

  async function handleNewVersion(event) {
    event.preventDefault()
    if (!latest) return
    setSavingVersion(true)
    setError('')
    try {
      await createPromptTemplateVersion(latest.id, { body: editingBody })
      await load()
      onChanged()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save this version.'))
    } finally {
      setSavingVersion(false)
    }
  }

  async function handleActivate(template) {
    setBusyId(template.id)
    try {
      await activatePromptTemplate(template.id)
      await load()
      onChanged()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not activate this version.'))
    } finally {
      setBusyId(null)
    }
  }

  async function handleDeactivate(template) {
    setBusyId(template.id)
    try {
      await deactivatePromptTemplate(template.id)
      await load()
      onChanged()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not deactivate this version.'))
    } finally {
      setBusyId(null)
    }
  }

  async function handleDelete(template) {
    if (!window.confirm(`Delete version ${template.version}? This cannot be undone.`)) return
    setBusyId(template.id)
    try {
      await deletePromptTemplate(template.id)
      await load()
      onChanged()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not delete this version.'))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <Modal title={latest ? latest.name : 'Template history'} onClose={onClose} width={640}>
      {error && <div className="alert alert-error">{error}</div>}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : (
        <>
          <form onSubmit={handleNewVersion} style={{ marginBottom: 20 }}>
            <label className="field">
              <span>Edit guidance text (saving creates a new version — the old one stays in history)</span>
              <textarea rows={6} value={editingBody} onChange={(e) => setEditingBody(e.target.value)} />
            </label>
            <button type="submit" className="btn btn-primary" disabled={savingVersion}>
              {savingVersion ? 'Saving…' : 'Save as new version'}
            </button>
          </form>

          <p className="page-subtitle" style={{ marginBottom: 8 }}>
            Version history ({versions.length})
          </p>
          <ul className="checklist">
            {versions.map((version) => (
              <li key={version.id}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <span>
                    v{version.version} — {new Date(version.created_at).toLocaleString()}{' '}
                    <span className={`badge badge-${version.is_active ? 'active' : 'inactive'}`}>
                      {version.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </span>
                  <span style={{ display: 'flex', gap: 4 }}>
                    {version.is_active ? (
                      <button
                        type="button"
                        className="btn-link"
                        disabled={busyId === version.id}
                        onClick={() => handleDeactivate(version)}
                      >
                        Deactivate
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn-link"
                        disabled={busyId === version.id}
                        onClick={() => handleActivate(version)}
                      >
                        Activate
                      </button>
                    )}
                    {!version.is_active && (
                      <button
                        type="button"
                        className="btn-link btn-link-danger"
                        disabled={busyId === version.id}
                        onClick={() => handleDelete(version)}
                      >
                        Delete
                      </button>
                    )}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </Modal>
  )
}
