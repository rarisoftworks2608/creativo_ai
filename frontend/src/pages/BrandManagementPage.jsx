import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  deleteBrandAsset,
  getBrandProfile,
  listBrandAssets,
  removeBrandImage,
  updateBrandProfile,
  uploadBrandAsset,
  uploadBrandImage,
} from '../api/brand'
import { getCompany } from '../api/companies'
import { extractErrorMessage } from '../api/client'
import BrandImageSlot from '../components/BrandImageSlot'
import ColorPaletteInput from '../components/ColorPaletteInput'
import ListOfObjectsInput from '../components/ListOfObjectsInput'
import Modal from '../components/Modal'
import TagsInput from '../components/TagsInput'

const TABS = [
  { key: 'identity', label: 'Brand Identity' },
  { key: 'guidelines', label: 'Brand Guidelines' },
  { key: 'marketing', label: 'Marketing Information' },
  { key: 'assets', label: 'Brand Assets' },
]

const ASSET_CATEGORIES = [
  { value: 'logo_upload', label: 'Logo uploads' },
  { value: 'reference_image', label: 'Reference images' },
  { value: 'product_image', label: 'Product images' },
  { value: 'document', label: 'Documents' },
  { value: 'marketing_material', label: 'Marketing materials' },
]

const IDENTITY_FIELDS = ['brand_colors', 'fonts', 'typography_notes']
const GUIDELINES_FIELDS = [
  'brand_voice', 'tone', 'writing_style', 'visual_style', 'dos', 'donts', 'keywords', 'restricted_words',
]
const MARKETING_FIELDS = ['customer_personas', 'offers', 'campaign_information']

function pick(source, keys) {
  return Object.fromEntries(keys.map((key) => [key, source[key]]))
}

export default function BrandManagementPage() {
  const { id: companyId } = useParams()

  const [company, setCompany] = useState(null)
  const [brand, setBrand] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [activeTab, setActiveTab] = useState('identity')

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const [companyData, brandData] = await Promise.all([getCompany(companyId), getBrandProfile(companyId)])
      setCompany(companyData)
      setBrand(brandData)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load brand information.'))
    } finally {
      setLoading(false)
    }
  }, [companyId])

  useEffect(() => {
    load()
  }, [load])

  if (loading) return <div className="page-loading">Loading…</div>
  if (loadError && !brand) return <div className="alert alert-error">{loadError}</div>
  if (!brand || !company) return null

  return (
    <div>
      <Link to={`/companies/${companyId}`} className="back-link">
        ← Back to {company.name}
      </Link>

      <div className="page-header">
        <div>
          <h1>Brand Management</h1>
          <p className="page-subtitle">{company.name}</p>
        </div>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      <div className="view-toggle brand-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={activeTab === tab.key ? 'active' : ''}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'identity' && <IdentitySection companyId={companyId} brand={brand} setBrand={setBrand} />}
      {activeTab === 'guidelines' && (
        <GuidelinesSection companyId={companyId} brand={brand} setBrand={setBrand} />
      )}
      {activeTab === 'marketing' && (
        <MarketingSection companyId={companyId} company={company} brand={brand} setBrand={setBrand} />
      )}
      {activeTab === 'assets' && <AssetsSection companyId={companyId} />}
    </div>
  )
}

// renderEdit/renderView are functions, not elements, so only the active branch is
// ever evaluated — the edit branch usually reads from a draft `form` state that is
// only populated once editing starts, so building it eagerly would crash while null.
function EditableCard({ title, renderEdit, renderView, editing, onEdit, onCancel, onSave, saving, error }) {
  return (
    <div className="card">
      <div className="card-header">
        <h2>{title}</h2>
        {!editing && (
          <button type="button" className="btn btn-ghost" onClick={onEdit}>
            Edit
          </button>
        )}
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {editing ? (
        <form
          onSubmit={(event) => {
            event.preventDefault()
            onSave()
          }}
        >
          {renderEdit()}
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onCancel}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </form>
      ) : (
        renderView()
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

// ---------- Brand Identity ----------

function IdentitySection({ companyId, brand, setBrand }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function startEditing() {
    setForm(pick(brand, IDENTITY_FIELDS))
    setError('')
    setEditing(true)
  }

  async function handleSave() {
    setSaving(true)
    setError('')
    try {
      const updated = await updateBrandProfile(companyId, form)
      setBrand(updated)
      setEditing(false)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save changes.'))
    } finally {
      setSaving(false)
    }
  }

  async function handleImageUpload(slot, file) {
    const updated = await uploadBrandImage(companyId, slot.replace('_', '-'), file)
    setBrand(updated)
  }

  async function handleImageRemove(slot) {
    const updated = await removeBrandImage(companyId, slot.replace('_', '-'))
    setBrand(updated)
  }

  return (
    <>
      <div className="card">
        <div className="card-header">
          <h2>Logo &amp; Favicon</h2>
        </div>
        <div className="image-slot-grid">
          <BrandImageSlot
            label="Logo"
            hint="Primary logo, used across creatives."
            imageUrl={brand.logo}
            onUpload={(file) => handleImageUpload('logo', file)}
            onRemove={() => handleImageRemove('logo')}
          />
          <BrandImageSlot
            label="Secondary logo"
            hint="Alternate/reversed logo for dark backgrounds."
            imageUrl={brand.secondary_logo}
            onUpload={(file) => handleImageUpload('secondary_logo', file)}
            onRemove={() => handleImageRemove('secondary_logo')}
          />
          <BrandImageSlot
            label="Favicon"
            hint="Small square icon."
            imageUrl={brand.favicon}
            onUpload={(file) => handleImageUpload('favicon', file)}
            onRemove={() => handleImageRemove('favicon')}
          />
        </div>
      </div>

      <EditableCard
        title="Colors &amp; Typography"
        editing={editing}
        onEdit={startEditing}
        onCancel={() => setEditing(false)}
        onSave={handleSave}
        saving={saving}
        error={error}
        renderEdit={() => (
          <>
            <label className="field">
              <span>Brand colors</span>
              <ColorPaletteInput value={form.brand_colors} onChange={(v) => setForm((p) => ({ ...p, brand_colors: v }))} />
            </label>
            <label className="field">
              <span>Fonts</span>
              <ListOfObjectsInput
                value={form.fonts}
                onChange={(v) => setForm((p) => ({ ...p, fonts: v }))}
                fields={[
                  { key: 'name', placeholder: 'Font name, e.g. Poppins' },
                  { key: 'usage', placeholder: 'Usage, e.g. Headings' },
                ]}
                addLabel="+ Add font"
              />
            </label>
            <label className="field">
              <span>Typography notes</span>
              <textarea
                rows={3}
                value={form.typography_notes}
                onChange={(e) => setForm((p) => ({ ...p, typography_notes: e.target.value }))}
              />
            </label>
          </>
        )}
        renderView={() => (
          <>
            <div className="field">
              <span className="field-view-label">Brand colors</span>
              {brand.brand_colors.length === 0 ? (
                <p className="muted">Not set</p>
              ) : (
                <div className="color-swatch-list">
                  {brand.brand_colors.map((color, i) => (
                    <div className="color-swatch" key={i}>
                      <span className="color-swatch-dot" style={{ background: color.hex }} />
                      <span>{color.name || color.hex}</span>
                      <code>{color.hex}</code>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <dl className="detail-list">
              <InfoRow
                label="Fonts"
                value={brand.fonts.length ? brand.fonts.map((f) => `${f.name}${f.usage ? ` (${f.usage})` : ''}`) : []}
              />
              <InfoRow label="Typography notes" value={brand.typography_notes} />
            </dl>
          </>
        )}
      />
    </>
  )
}

// ---------- Brand Guidelines ----------

function GuidelinesSection({ companyId, brand, setBrand }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function startEditing() {
    setForm(pick(brand, GUIDELINES_FIELDS))
    setError('')
    setEditing(true)
  }

  async function handleSave() {
    setSaving(true)
    setError('')
    try {
      const updated = await updateBrandProfile(companyId, form)
      setBrand(updated)
      setEditing(false)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save changes.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <EditableCard
      title="Brand Guidelines"
      editing={editing}
      onEdit={startEditing}
      onCancel={() => setEditing(false)}
      onSave={handleSave}
      saving={saving}
      error={error}
      renderEdit={() => (
        <>
          <div className="field-row">
            <label className="field">
              <span>Brand voice</span>
              <textarea rows={2} value={form.brand_voice} onChange={(e) => setForm((p) => ({ ...p, brand_voice: e.target.value }))} />
            </label>
            <label className="field">
              <span>Tone</span>
              <textarea rows={2} value={form.tone} onChange={(e) => setForm((p) => ({ ...p, tone: e.target.value }))} />
            </label>
          </div>
          <div className="field-row">
            <label className="field">
              <span>Writing style</span>
              <textarea rows={2} value={form.writing_style} onChange={(e) => setForm((p) => ({ ...p, writing_style: e.target.value }))} />
            </label>
            <label className="field">
              <span>Visual style</span>
              <textarea rows={2} value={form.visual_style} onChange={(e) => setForm((p) => ({ ...p, visual_style: e.target.value }))} />
            </label>
          </div>
          <label className="field">
            <span>Do's</span>
            <TagsInput value={form.dos} onChange={(v) => setForm((p) => ({ ...p, dos: v }))} placeholder="Type a do, press Enter" />
          </label>
          <label className="field">
            <span>Don'ts</span>
            <TagsInput value={form.donts} onChange={(v) => setForm((p) => ({ ...p, donts: v }))} placeholder="Type a don't, press Enter" />
          </label>
          <label className="field">
            <span>Keywords</span>
            <TagsInput value={form.keywords} onChange={(v) => setForm((p) => ({ ...p, keywords: v }))} placeholder="Type a keyword, press Enter" />
          </label>
          <label className="field">
            <span>Restricted words</span>
            <TagsInput
              value={form.restricted_words}
              onChange={(v) => setForm((p) => ({ ...p, restricted_words: v }))}
              placeholder="Type a restricted word, press Enter"
            />
          </label>
        </>
      )}
      renderView={() => (
        <dl className="detail-list">
          <InfoRow label="Brand voice" value={brand.brand_voice} />
          <InfoRow label="Tone" value={brand.tone} />
          <InfoRow label="Writing style" value={brand.writing_style} />
          <InfoRow label="Visual style" value={brand.visual_style} />
          <InfoRow label="Do's" value={brand.dos} />
          <InfoRow label="Don'ts" value={brand.donts} />
          <InfoRow label="Keywords" value={brand.keywords} />
          <InfoRow label="Restricted words" value={brand.restricted_words} />
        </dl>
      )}
    />
  )
}

// ---------- Marketing Information ----------

function MarketingSection({ companyId, company, brand, setBrand }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function startEditing() {
    setForm(pick(brand, MARKETING_FIELDS))
    setError('')
    setEditing(true)
  }

  async function handleSave() {
    setSaving(true)
    setError('')
    try {
      const updated = await updateBrandProfile(companyId, form)
      setBrand(updated)
      setEditing(false)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save changes.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="card">
        <div className="card-header">
          <h2>Business Profile</h2>
          <Link to={`/companies/${companyId}`} className="btn-link">
            Edit in company details
          </Link>
        </div>
        <p className="modal-hint">Target audience, products, services, USP and competitors are managed on the company profile.</p>
        <dl className="detail-list">
          <InfoRow label="Target audience" value={company.target_audience} />
          <InfoRow label="Products" value={company.products} />
          <InfoRow label="Services" value={company.services} />
          <InfoRow label="USP" value={company.usp} />
          <InfoRow label="Competitors" value={company.competitors} />
        </dl>
      </div>

      <EditableCard
        title="Personas, Offers &amp; Campaigns"
        editing={editing}
        onEdit={startEditing}
        onCancel={() => setEditing(false)}
        onSave={handleSave}
        saving={saving}
        error={error}
        renderEdit={() => (
          <>
            <label className="field">
              <span>Customer personas</span>
              <ListOfObjectsInput
                value={form.customer_personas}
                onChange={(v) => setForm((p) => ({ ...p, customer_personas: v }))}
                fields={[
                  { key: 'name', placeholder: 'Persona name, e.g. Busy Parent' },
                  { key: 'summary', placeholder: 'Short description' },
                ]}
                addLabel="+ Add persona"
              />
            </label>
            <label className="field">
              <span>Offers</span>
              <TagsInput value={form.offers} onChange={(v) => setForm((p) => ({ ...p, offers: v }))} placeholder="Type an offer, press Enter" />
            </label>
            <label className="field">
              <span>Campaign information</span>
              <textarea
                rows={3}
                value={form.campaign_information}
                onChange={(e) => setForm((p) => ({ ...p, campaign_information: e.target.value }))}
              />
            </label>
          </>
        )}
        renderView={() => (
          <>
            <div className="field">
              <span className="field-view-label">Customer personas</span>
              {brand.customer_personas.length === 0 ? (
                <p className="muted">Not set</p>
              ) : (
                <div className="persona-list">
                  {brand.customer_personas.map((persona, i) => (
                    <div className="persona-card" key={i}>
                      <div className="persona-name">{persona.name}</div>
                      {persona.summary && <div className="persona-summary">{persona.summary}</div>}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <dl className="detail-list">
              <InfoRow label="Offers" value={brand.offers} />
              <InfoRow label="Campaign information" value={brand.campaign_information} />
            </dl>
          </>
        )}
      />
    </>
  )
}

// ---------- Brand Assets ----------

function AssetsSection({ companyId }) {
  const [assets, setAssets] = useState([])
  const [category, setCategory] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showUpload, setShowUpload] = useState(false)
  const [uploadForm, setUploadForm] = useState({ category: 'reference_image', name: '', file: null })
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [deletingId, setDeletingId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await listBrandAssets(companyId, { category: category || undefined })
      setAssets(data.results)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load brand assets.'))
    } finally {
      setLoading(false)
    }
  }, [companyId, category])

  useEffect(() => {
    load()
  }, [load])

  async function handleUpload(event) {
    event.preventDefault()
    if (!uploadForm.file) {
      setUploadError('Choose a file to upload.')
      return
    }
    setUploading(true)
    setUploadError('')
    try {
      const created = await uploadBrandAsset(companyId, uploadForm)
      setAssets((prev) => [created, ...prev])
      setShowUpload(false)
      setUploadForm({ category: 'reference_image', name: '', file: null })
    } catch (err) {
      setUploadError(extractErrorMessage(err, 'Could not upload this file.'))
    } finally {
      setUploading(false)
    }
  }

  async function handleDelete(assetId) {
    setDeletingId(assetId)
    try {
      await deleteBrandAsset(companyId, assetId)
      setAssets((prev) => prev.filter((a) => a.id !== assetId))
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not delete this asset.'))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <h2>Brand Assets</h2>
        <button type="button" className="btn btn-primary" onClick={() => setShowUpload(true)}>
          + Upload asset
        </button>
      </div>

      <div className="toolbar">
        <select className="status-select" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {ASSET_CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading ? (
        <div className="page-loading">Loading…</div>
      ) : assets.length === 0 ? (
        <div className="empty-state">
          <p>No assets uploaded yet.</p>
        </div>
      ) : (
        <div className="asset-grid">
          {assets.map((asset) => (
            <div className="asset-card" key={asset.id}>
              <a href={asset.file} target="_blank" rel="noreferrer" className="asset-thumb">
                {/\.(png|jpe?g|gif|webp|svg)$/i.test(asset.file) ? (
                  <img src={asset.file} alt={asset.name} />
                ) : (
                  <span className="asset-thumb-icon">📄</span>
                )}
              </a>
              <div className="asset-meta">
                <div className="asset-name" title={asset.name}>
                  {asset.name}
                </div>
                <div className="asset-category">{ASSET_CATEGORIES.find((c) => c.value === asset.category)?.label}</div>
              </div>
              <button
                type="button"
                className="btn-link btn-link-danger"
                disabled={deletingId === asset.id}
                onClick={() => handleDelete(asset.id)}
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}

      {showUpload && (
        <Modal title="Upload brand asset" onClose={() => setShowUpload(false)}>
          <form onSubmit={handleUpload}>
            {uploadError && <div className="alert alert-error">{uploadError}</div>}
            <label className="field">
              <span>Category *</span>
              <select
                value={uploadForm.category}
                onChange={(e) => setUploadForm((p) => ({ ...p, category: e.target.value }))}
                required
              >
                {ASSET_CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>File *</span>
              <input
                type="file"
                required
                onChange={(e) => setUploadForm((p) => ({ ...p, file: e.target.files?.[0] || null }))}
              />
            </label>
            <label className="field">
              <span>Name</span>
              <input
                value={uploadForm.name}
                placeholder="Defaults to the file name"
                onChange={(e) => setUploadForm((p) => ({ ...p, name: e.target.value }))}
              />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setShowUpload(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={uploading}>
                {uploading ? 'Uploading…' : 'Upload'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
