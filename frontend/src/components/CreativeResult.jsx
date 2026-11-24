import { useState } from 'react'
import Modal from './Modal'
import VariationGrid from './VariationGrid'

const STATUS_LABELS = { pending: 'Pending', queued: 'Queued', processing: 'Generating', succeeded: 'Ready', failed: 'Failed' }
const IN_PROGRESS = ['pending', 'queued', 'processing']
const ROLE_LABELS = { cover: 'Cover', content: 'Content', cta: 'Call to action' }

/** The inputs this creative was made from, as short labelled chips. */
function inputSummary(request, options) {
  const fields = request.brief_fields || {}
  const chips = []
  const style = options?.design_styles.find((item) => item.value === request.design_style)
  if (request.resolved_aspect_ratio) chips.push(request.resolved_aspect_ratio)
  if (style) chips.push(style.label)
  if (request.creative_type === 'carousel' && request.slide_count) chips.push(`${request.slide_count} slides`)
  if (fields.festival) {
    const festival = options?.festivals.find((item) => item.value === fields.festival)
    chips.push(fields.festival === 'custom' ? fields.festival_name : festival?.label || fields.festival)
  }
  if (fields.category) {
    const category = options?.announcement_categories.find((item) => item.value === fields.category)
    chips.push(category?.label || fields.category)
  }
  if (fields.objective && request.creative_type === 'story') {
    const objective = options?.story_objectives.find((item) => item.value === fields.objective)
    chips.push(objective?.label || fields.objective)
  }
  return chips.filter(Boolean)
}

function headlineOf(request) {
  const fields = request.brief_fields || {}
  return fields.topic || fields.title || fields.headline || (fields.quote ? `“${fields.quote}”` : '') || request.prompt_brief
}

export function EditTextModal({ variation, isSlide, onSave, onClose }) {
  const [form, setForm] = useState({
    eyebrow: variation.eyebrow || '',
    headline: variation.headline || '',
    description: variation.description || '',
    cta: variation.cta || '',
    caption: variation.caption || '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const editable = variation.can_edit

  async function handleSubmit(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await onSave(editable ? form : { caption: form.caption })
      onClose()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not save the text.')
    } finally {
      setSaving(false)
    }
  }

  const set = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }))
  return (
    <Modal title={`Edit text · ${isSlide ? 'slide' : 'variation'} ${variation.variation_number}`} onClose={onClose} width={560}>
      <form onSubmit={handleSubmit}>
        {error && <div className="alert alert-error">{error}</div>}
        {editable ? (
          <p className="modal-hint">The image is re-rendered with your text straight away - no AI credit is used.</p>
        ) : (
          <p className="modal-hint">This creative was made before editable text was available, so only the post caption can be changed. Regenerate it to edit the text on the image.</p>
        )}
        {editable && (
          <>
            <label className="field">
              <span>Label above the headline</span>
              <input value={form.eyebrow} onChange={set('eyebrow')} />
            </label>
            <label className="field">
              <span>Headline</span>
              <textarea rows={2} value={form.headline} onChange={set('headline')} />
            </label>
            <label className="field">
              <span>Supporting text</span>
              <textarea rows={2} value={form.description} onChange={set('description')} />
            </label>
            <label className="field">
              <span>Call to action</span>
              <input value={form.cta} onChange={set('cta')} />
            </label>
          </>
        )}
        <label className="field">
          <span>Post caption</span>
          <textarea rows={3} value={form.caption} onChange={set('caption')} />
        </label>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving…' : editable ? 'Save & re-render' : 'Save caption'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

/** A carousel: one large slide with previous / next, the strip of all slides, and per-slide actions. */
function SlideViewer({ slides, canManage, onEdit, onRegenerate }) {
  const [index, setIndex] = useState(0)
  const current = slides[Math.min(index, slides.length - 1)]
  if (!current) return null
  const busy = current.status === 'processing'
  const go = (step) => setIndex((prev) => (prev + step + slides.length) % slides.length)

  return (
    <div className="slide-viewer">
      <div className="slide-stage">
        <button type="button" className="slide-nav slide-nav-prev" onClick={() => go(-1)} aria-label="Previous slide">
          ‹
        </button>
        <div className="slide-frame">
          <img src={current.image} alt={`Slide ${current.variation_number}`} />
          {busy && <div className="slide-busy">Regenerating this slide…</div>}
        </div>
        <button type="button" className="slide-nav slide-nav-next" onClick={() => go(1)} aria-label="Next slide">
          ›
        </button>
      </div>

      <div className="slide-meta">
        <div>
          <strong>
            Slide {current.variation_number} of {slides.length}
          </strong>
          <span className="slide-role">{ROLE_LABELS[current.slide_role] || ''}</span>
          {current.headline && <p>{current.headline}</p>}
          {current.status === 'failed' && <div className="alert alert-error">{current.error_message || 'Regeneration failed.'}</div>}
        </div>
        <div className="slide-actions">
          <a className="btn btn-ghost btn-sm" href={current.image} download target="_blank" rel="noreferrer">
            Download slide
          </a>
          {canManage && (
            <>
              <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => onEdit(current)}>
                Edit text
              </button>
              <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => onRegenerate(current)}>
                Regenerate slide
              </button>
            </>
          )}
        </div>
      </div>

      <ol className="slide-strip" aria-label="All slides">
        {slides.map((slide, position) => (
          <li key={slide.id}>
            <button
              type="button"
              className={`slide-thumb ${position === index ? 'active' : ''} ${slide.status === 'processing' ? 'busy' : ''}`}
              onClick={() => setIndex(position)}
              aria-label={`Slide ${slide.variation_number}`}
              aria-current={position === index ? 'true' : undefined}
            >
              <img src={slide.image} alt="" />
              <span>{String(slide.variation_number).padStart(2, '0')}</span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  )
}

/** One generation: its inputs, status, and the finished creative with its actions. */
export default function CreativeResult({ request, options, canManage, onRetry, onSelect, onEdit, onRegenerate, onDownload }) {
  const [editing, setEditing] = useState(null)
  const inProgress = IN_PROGRESS.includes(request.status)
  const isCarousel = request.creative_type === 'carousel'
  const chips = inputSummary(request, options)
  const title = headlineOf(request)
  const count = isCarousel ? request.slide_count || request.variations.length : request.variation_count

  return (
    <div className="card request-card creative-result">
      <div className="card-header card-header-wrap">
        <div>
          <h2>
            {request.creative_type_display}
            {request.platform_display ? <span className="cr-platform"> · {request.platform_display}</span> : null}
          </h2>
          {title && <p className="cr-title">{title}</p>}
          <div className="cr-chips">
            {chips.map((chip) => (
              <span key={chip} className="cr-chip">
                {chip}
              </span>
            ))}
            <span className="cr-date">{new Date(request.created_at).toLocaleString()}</span>
          </div>
        </div>
        <div className="card-header-actions">
          <span className={`badge status-badge gen-status-${request.status}`}>{STATUS_LABELS[request.status]}</span>
          {request.status === 'succeeded' && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={onDownload}>
              {isCarousel ? 'Download all slides' : 'Download all'}
            </button>
          )}
        </div>
      </div>

      {inProgress && (
        <div className="cr-progress">
          <span className="cr-spinner" aria-hidden="true" />
          Generating {count} {isCarousel ? 'slides' : count === 1 ? 'image' : 'images'}… this can take a minute.
        </div>
      )}

      {request.status === 'failed' && (
        <>
          <div className="alert alert-error">{request.error_message}</div>
          {canManage && (
            <button type="button" className="btn btn-ghost" onClick={onRetry}>
              Retry
            </button>
          )}
        </>
      )}

      {request.status === 'succeeded' &&
        (isCarousel ? (
          <SlideViewer slides={request.variations} canManage={canManage} onEdit={setEditing} onRegenerate={onRegenerate} />
        ) : (
          <VariationGrid
            variations={request.variations}
            onSelect={onSelect}
            onEdit={canManage ? setEditing : undefined}
            onRegenerate={canManage ? onRegenerate : undefined}
          />
        ))}

      {editing && (
        <EditTextModal
          variation={editing}
          isSlide={isCarousel}
          onSave={(payload) => onEdit(editing, payload)}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  )
}
