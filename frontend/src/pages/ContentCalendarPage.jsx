import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getCompany } from '../api/companies'
import {
  commitCalendarImport,
  createCalendarItem,
  deleteCalendarItem,
  downloadCalendarTemplate,
  duplicateCalendarItem,
  listCalendarItems,
  previewCalendarImport,
  updateCalendarItem,
} from '../api/contentCalendar'
import { extractErrorMessage } from '../api/client'
import Modal from '../components/Modal'
import TagsInput from '../components/TagsInput'

// Suggestions only - Category and Format are free text so each client's own
// planning vocabulary (weekly themes, format names, etc.) is never rejected.
const CATEGORY_SUGGESTIONS = ['Promotional', 'Educational', 'Festival', 'Product', 'Announcement', 'Testimonial']

const CONTENT_TYPE_SUGGESTIONS = [
  'Single Image', 'Carousel', 'Grid', 'Story', 'Reel', 'Short Video',
  'Static Post', 'Static + Story', 'Complimentary Creative', 'Video',
]

const PLATFORM_OPTIONS = [
  ['instagram', 'Instagram'], ['facebook', 'Facebook'], ['linkedin', 'LinkedIn'],
  ['twitter', 'X (Twitter)'], ['pinterest', 'Pinterest'],
]

const STATUS_OPTIONS = [
  ['draft', 'Draft'], ['scheduled', 'Scheduled'], ['generating', 'Generating'], ['generated', 'Generated'],
  ['pending_approval', 'Pending Approval'], ['approved', 'Approved'], ['rejected', 'Rejected'],
  ['published', 'Published'], ['failed', 'Failed'],
]

const STATUS_LABELS = Object.fromEntries(STATUS_OPTIONS)
const PLATFORM_LABELS = Object.fromEntries(PLATFORM_OPTIONS)

const EMPTY_ITEM_FORM = {
  topic: '', category: '', weekly_theme: '', content_type: '', platforms: [],
  objective: '', campaign: '', scheduled_date: '', scheduled_time: '',
  caption_requirements: '', creative_requirements: '', cta: '', hashtags: [],
  source_notes: '', status: 'draft',
}

export default function ContentCalendarPage() {
  const { id: companyId } = useParams()
  const fileInputRef = useRef(null)

  const [company, setCompany] = useState(null)
  const [items, setItems] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [statusFilter, setStatusFilter] = useState('')
  const [platformFilter, setPlatformFilter] = useState('')
  const [search, setSearch] = useState('')

  const [showChoice, setShowChoice] = useState(false)
  const [showItemForm, setShowItemForm] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [itemForm, setItemForm] = useState(EMPTY_ITEM_FORM)
  const [itemFormError, setItemFormError] = useState('')
  const [savingItem, setSavingItem] = useState(false)

  const [showImport, setShowImport] = useState(false)
  const [importFile, setImportFile] = useState(null)
  const [importPreview, setImportPreview] = useState(null)
  const [importError, setImportError] = useState('')
  const [importBusy, setImportBusy] = useState(false)
  const [importResult, setImportResult] = useState(null)

  const [busyItemId, setBusyItemId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const [companyData, itemsData] = await Promise.all([
        getCompany(companyId),
        listCalendarItems(companyId, { status: statusFilter, platform: platformFilter, search }),
      ])
      setCompany(companyData)
      setItems(itemsData.results)
      setCount(itemsData.count)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load the content calendar.'))
    } finally {
      setLoading(false)
    }
  }, [companyId, statusFilter, platformFilter, search])

  useEffect(() => {
    const timeout = setTimeout(load, 250)
    return () => clearTimeout(timeout)
  }, [load])

  function openCreateForm() {
    setEditingItem(null)
    setItemForm(EMPTY_ITEM_FORM)
    setItemFormError('')
    setShowChoice(false)
    setShowItemForm(true)
  }

  function openEditForm(item) {
    setEditingItem(item)
    setItemForm({
      topic: item.topic,
      category: item.category,
      weekly_theme: item.weekly_theme,
      content_type: item.content_type,
      platforms: item.platforms,
      objective: item.objective,
      campaign: item.campaign,
      scheduled_date: item.scheduled_date,
      scheduled_time: item.scheduled_time || '',
      caption_requirements: item.caption_requirements,
      creative_requirements: item.creative_requirements,
      cta: item.cta,
      hashtags: item.hashtags,
      source_notes: item.source_notes,
      status: item.status,
    })
    setItemFormError('')
    setShowItemForm(true)
  }

  function updateItemField(field, value) {
    setItemForm((prev) => ({ ...prev, [field]: value }))
  }

  function togglePlatform(code) {
    setItemForm((prev) => ({
      ...prev,
      platforms: prev.platforms.includes(code)
        ? prev.platforms.filter((p) => p !== code)
        : [...prev.platforms, code],
    }))
  }

  async function handleSaveItem(event) {
    event.preventDefault()
    setSavingItem(true)
    setItemFormError('')
    try {
      const payload = { ...itemForm, scheduled_time: itemForm.scheduled_time || null }
      if (editingItem) {
        await updateCalendarItem(companyId, editingItem.id, payload)
      } else {
        await createCalendarItem(companyId, payload)
      }
      setShowItemForm(false)
      await load()
    } catch (err) {
      setItemFormError(extractErrorMessage(err, 'Could not save this content item.'))
    } finally {
      setSavingItem(false)
    }
  }

  async function handleDelete(item) {
    if (!window.confirm(`Delete "${item.topic}"? This cannot be undone.`)) return
    setBusyItemId(item.id)
    try {
      await deleteCalendarItem(companyId, item.id)
      setItems((prev) => prev.filter((i) => i.id !== item.id))
      setCount((prev) => prev - 1)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not delete this item.'))
    } finally {
      setBusyItemId(null)
    }
  }

  async function handleDuplicate(item) {
    setBusyItemId(item.id)
    try {
      await duplicateCalendarItem(companyId, item.id)
      await load()
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not duplicate this item.'))
    } finally {
      setBusyItemId(null)
    }
  }

  function openImportModal() {
    setShowChoice(false)
    setImportFile(null)
    setImportPreview(null)
    setImportResult(null)
    setImportError('')
    setShowImport(true)
  }

  function handleFileChange(event) {
    const file = event.target.files?.[0] || null
    setImportFile(file)
    setImportPreview(null)
    setImportResult(null)
    setImportError('')
  }

  async function handlePreview() {
    if (!importFile) return
    setImportBusy(true)
    setImportError('')
    try {
      const preview = await previewCalendarImport(companyId, importFile)
      setImportPreview(preview)
    } catch (err) {
      setImportError(extractErrorMessage(err, 'Could not read this file.'))
    } finally {
      setImportBusy(false)
    }
  }

  async function handleConfirmImport() {
    if (!importFile) return
    setImportBusy(true)
    setImportError('')
    try {
      const result = await commitCalendarImport(companyId, importFile)
      setImportResult(result)
      setImportPreview(null)
      await load()
    } catch (err) {
      setImportError(extractErrorMessage(err, 'Could not import this file.'))
    } finally {
      setImportBusy(false)
    }
  }

  if (loading && !company) return <div className="page-loading">Loading…</div>

  return (
    <div>
      <Link to={`/companies/${companyId}`} className="back-link">
        ← Back to {company?.name || 'company'}
      </Link>

      <div className="page-header">
        <div>
          <h1>Content calendar</h1>
          <p className="page-subtitle">
            {company?.name} · {count} item{count === 1 ? '' : 's'}
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowChoice(true)}>
          + Add content
        </button>
      </div>

      <div className="toolbar">
        <input
          type="search"
          placeholder="Search by topic…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="search-input"
        />
        <select className="status-select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <select className="status-select" value={platformFilter} onChange={(e) => setPlatformFilter(e.target.value)}>
          <option value="">All platforms</option>
          {PLATFORM_OPTIONS.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      <div className="card">
        {loading ? (
          <div className="empty-state">Loading…</div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <p>No content scheduled yet.</p>
            <button type="button" className="btn btn-primary" onClick={() => setShowChoice(true)}>
              Add your first content item
            </button>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Topic</th>
                  <th>Weekly theme</th>
                  <th>Format</th>
                  <th>Platforms</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      {item.scheduled_date}
                      {item.scheduled_time ? ` · ${item.scheduled_time.slice(0, 5)}` : ''}
                    </td>
                    <td>{item.topic}</td>
                    <td>{item.weekly_theme || item.category || '—'}</td>
                    <td>{item.content_type}</td>
                    <td>
                      <div className="tag-list">
                        {item.platforms.map((p) => (
                          <span key={p} className="tag-chip tag-chip-static">{PLATFORM_LABELS[p] || p}</span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <span className={`badge status-badge status-${item.status}`}>
                        {STATUS_LABELS[item.status] || item.status}
                      </span>
                    </td>
                    <td className="table-actions">
                      <button type="button" className="btn-link" onClick={() => openEditForm(item)}>
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn-link"
                        disabled={busyItemId === item.id}
                        onClick={() => handleDuplicate(item)}
                      >
                        Duplicate
                      </button>
                      <button
                        type="button"
                        className="btn-link btn-link-danger"
                        disabled={busyItemId === item.id}
                        onClick={() => handleDelete(item)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showChoice && (
        <Modal title="Add content" onClose={() => setShowChoice(false)} width={560}>
          <p className="modal-hint">How do you want to add content to this calendar?</p>
          <div className="choice-grid">
            <button type="button" className="choice-card" onClick={openCreateForm}>
              <span className="choice-icon" aria-hidden="true">✎</span>
              <span className="choice-title">Create manually</span>
              <span className="choice-desc">Fill in one content item using a form.</span>
            </button>
            <button type="button" className="choice-card" onClick={openImportModal}>
              <span className="choice-icon" aria-hidden="true">⇪</span>
              <span className="choice-title">Upload Excel</span>
              <span className="choice-desc">Import a whole month at once from a spreadsheet.</span>
            </button>
          </div>
        </Modal>
      )}

      {showItemForm && (
        <Modal title={editingItem ? 'Edit content' : 'Create content'} onClose={() => setShowItemForm(false)} width={640}>
          <form onSubmit={handleSaveItem}>
            {itemFormError && <div className="alert alert-error">{itemFormError}</div>}

            <label className="field">
              <span>Topical *</span>
              <input
                value={itemForm.topic}
                onChange={(e) => updateItemField('topic', e.target.value)}
                placeholder="e.g. National Doctor's Day"
                required
                autoFocus
              />
            </label>

            <div className="field-row">
              <label className="field">
                <span>Weekly theme</span>
                <input
                  value={itemForm.weekly_theme}
                  onChange={(e) => updateItemField('weekly_theme', e.target.value)}
                  placeholder="e.g. Leadership, Community"
                />
              </label>
              <label className="field">
                <span>Format *</span>
                <input
                  list="content-type-suggestions"
                  value={itemForm.content_type}
                  onChange={(e) => updateItemField('content_type', e.target.value)}
                  placeholder="e.g. Static Post, Reel"
                  required
                />
                <datalist id="content-type-suggestions">
                  {CONTENT_TYPE_SUGGESTIONS.map((option) => (
                    <option key={option} value={option} />
                  ))}
                </datalist>
              </label>
            </div>

            <div className="field">
              <span>Platforms *</span>
              <div className="checkbox-row">
                {PLATFORM_OPTIONS.map(([value, label]) => (
                  <label key={value} className="field-checkbox field-checkbox-inline">
                    <input
                      type="checkbox"
                      checked={itemForm.platforms.includes(value)}
                      onChange={() => togglePlatform(value)}
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="field-row">
              <label className="field">
                <span>Date *</span>
                <input
                  type="date"
                  value={itemForm.scheduled_date}
                  onChange={(e) => updateItemField('scheduled_date', e.target.value)}
                  required
                />
              </label>
              <label className="field">
                <span>Post time</span>
                <input
                  type="time"
                  value={itemForm.scheduled_time}
                  onChange={(e) => updateItemField('scheduled_time', e.target.value)}
                />
              </label>
            </div>

            <div className="field-row">
              <label className="field">
                <span>Category</span>
                <input
                  list="category-suggestions"
                  value={itemForm.category}
                  onChange={(e) => updateItemField('category', e.target.value)}
                  placeholder="Optional internal classification"
                />
                <datalist id="category-suggestions">
                  {CATEGORY_SUGGESTIONS.map((option) => (
                    <option key={option} value={option} />
                  ))}
                </datalist>
              </label>
              <label className="field">
                <span>Campaign</span>
                <input value={itemForm.campaign} onChange={(e) => updateItemField('campaign', e.target.value)} />
              </label>
            </div>

            <label className="field">
              <span>Objective</span>
              <input value={itemForm.objective} onChange={(e) => updateItemField('objective', e.target.value)} />
            </label>

            <label className="field">
              <span>Caption / content idea</span>
              <textarea
                rows={2}
                value={itemForm.caption_requirements}
                onChange={(e) => updateItemField('caption_requirements', e.target.value)}
              />
            </label>
            <label className="field">
              <span>Visual brief</span>
              <textarea
                rows={2}
                value={itemForm.creative_requirements}
                onChange={(e) => updateItemField('creative_requirements', e.target.value)}
              />
            </label>

            <div className="field-row">
              <label className="field">
                <span>CTA</span>
                <input value={itemForm.cta} onChange={(e) => updateItemField('cta', e.target.value)} />
              </label>
              <label className="field">
                <span>Status</span>
                <select value={itemForm.status} onChange={(e) => updateItemField('status', e.target.value)}>
                  {STATUS_OPTIONS.map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
            </div>

            <label className="field">
              <span>Hashtags</span>
              <TagsInput
                value={itemForm.hashtags}
                onChange={(v) => updateItemField('hashtags', v)}
                placeholder="Type a hashtag, press Enter"
              />
            </label>

            <label className="field">
              <span>Source</span>
              <input
                value={itemForm.source_notes}
                onChange={(e) => updateItemField('source_notes', e.target.value)}
                placeholder="Optional reference / inspiration link"
              />
            </label>

            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setShowItemForm(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={savingItem || itemForm.platforms.length === 0}>
                {savingItem ? 'Saving…' : editingItem ? 'Save changes' : 'Create content'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {showImport && (
        <Modal title="Upload Excel calendar" onClose={() => setShowImport(false)} width={720}>
          {!importResult ? (
            <>
              <p className="modal-hint">
                Upload a .xlsx file to bulk-add content. Columns are matched by name (Date, Platform, Format,
                Topical, Weekly Theme, Post Time, Caption / Content Idea, Visual Brief, Hashtags + CTA, Status,
                Source) — column order doesn't matter, and Status/Source can be left out.{' '}
                <button type="button" className="btn-link" onClick={() => downloadCalendarTemplate(companyId)}>
                  Download the template
                </button>
              </p>

              {importError && <div className="alert alert-error">{importError}</div>}

              <label className="field">
                <span>Excel file (.xlsx)</span>
                <input ref={fileInputRef} type="file" accept=".xlsx" onChange={handleFileChange} />
              </label>

              {importPreview && (
                <div className="import-preview">
                  <div className="import-summary">
                    <span className="import-summary-ok">{importPreview.valid_count} ready to import</span>
                    {importPreview.invalid_count > 0 && (
                      <span className="import-summary-bad">{importPreview.invalid_count} with errors</span>
                    )}
                  </div>

                  {importPreview.invalid_rows.length > 0 && (
                    <div className="table-wrapper import-error-table">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Row</th>
                            <th>Topic</th>
                            <th>Errors</th>
                          </tr>
                        </thead>
                        <tbody>
                          {importPreview.invalid_rows.map((row) => (
                            <tr key={row.row}>
                              <td>{row.row}</td>
                              <td>{row.data.topic || '—'}</td>
                              <td className="import-errors">{row.errors.join(' ')}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              <div className="modal-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setShowImport(false)}>
                  Cancel
                </button>
                {!importPreview ? (
                  <button type="button" className="btn btn-ghost" disabled={!importFile || importBusy} onClick={handlePreview}>
                    {importBusy ? 'Reading…' : 'Preview'}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={importBusy || importPreview.valid_count === 0}
                    onClick={handleConfirmImport}
                  >
                    {importBusy ? 'Importing…' : `Import ${importPreview.valid_count} item${importPreview.valid_count === 1 ? '' : 's'}`}
                  </button>
                )}
              </div>
            </>
          ) : (
            <>
              <p>
                Imported <strong>{importResult.created_count}</strong> item{importResult.created_count === 1 ? '' : 's'}.
                {importResult.invalid_count > 0 && ` ${importResult.invalid_count} row(s) were skipped due to errors.`}
              </p>
              <div className="modal-actions">
                <button type="button" className="btn btn-primary" onClick={() => setShowImport(false)}>
                  Done
                </button>
              </div>
            </>
          )}
        </Modal>
      )}
    </div>
  )
}
