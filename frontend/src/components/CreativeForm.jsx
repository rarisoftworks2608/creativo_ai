import { useMemo, useState } from 'react'
import ICONS from './DashboardIcons'

// What each type is for - shown on the type picker so the choice is obvious.
const TYPE_CARDS = {
  post: { icon: 'image', blurb: 'One clear message in a single image' },
  carousel: { icon: 'file', blurb: '3-10 slides that tell a story' },
  story: { icon: 'video', blurb: 'Vertical 9:16, made for phones' },
  festival_creative: { icon: 'sparkle', blurb: 'Greetings for festivals and occasions' },
  announcement_creative: { icon: 'send', blurb: 'Launches, openings, milestones, news' },
  testimonial_creative: { icon: 'users', blurb: "A real client's words, beautifully set" },
}

const PLATFORMS = [
  { value: 'instagram', label: 'Instagram' },
  { value: 'facebook', label: 'Facebook' },
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'general', label: 'General / multi-platform' },
]

const EXACT_HINT = 'Leave blank and the AI writes it. Anything you type appears on the creative exactly as written.'

const EMPTY_COMMON = {
  creative_type: 'post', platform: 'instagram', design_style: '', aspect_ratio: '', variation_count: 1,
  slide_count: 5, include_text_overlay: true, content_calendar_item: '', prompt_brief: '', product_info: '',
}

function Field({ label, hint, required, children }) {
  return (
    <label className="field">
      <span>
        {label}
        {required ? ' *' : ''}
      </span>
      {children}
      {hint && <small className="field-hint-inline">{hint}</small>}
    </label>
  )
}

/** A layout sketch of the creative at its real proportions - the picture itself is drawn by the AI. */
function LayoutPreview({ type, ratio, fields, slideCount, options }) {
  const aspect = options.aspect_ratios.find((item) => item.value === ratio)
  const [w, h] = aspect ? aspect.size : [1080, 1350]
  const lines = previewLines(type, fields, options)
  return (
    <div className="cf-preview">
      <div className="cf-preview-label">
        Layout preview · {aspect?.label || ratio}
        <span>
          {w} × {h}
        </span>
      </div>
      <div className={`cf-frame cf-frame-${type}`} style={{ aspectRatio: `${w} / ${h}` }}>
        {type === 'story' && (
          <>
            <span className="cf-safe cf-safe-top">App interface</span>
            <span className="cf-safe cf-safe-bottom">Reply bar</span>
          </>
        )}
        <span className="cf-logo">Logo</span>
        <div className="cf-text">
          {lines.eyebrow && <div className="cf-eyebrow">{lines.eyebrow}</div>}
          <div className={`cf-headline ${type === 'testimonial_creative' ? 'cf-quote' : ''}`}>{lines.headline}</div>
          {lines.body && <div className="cf-body">{lines.body}</div>}
          {lines.stars > 0 && <div className="cf-stars">{'★'.repeat(lines.stars)}</div>}
          {lines.cta && <div className="cf-cta">{lines.cta} →</div>}
        </div>
        {type === 'carousel' && (
          <div className="cf-dots">
            {Array.from({ length: slideCount }, (_, index) => (
              <span key={index} className={index === 0 ? 'on' : ''} />
            ))}
          </div>
        )}
      </div>
      <p className="cf-preview-note">
        {type === 'carousel'
          ? `Cover slide shown. Each of the ${slideCount} slides is its own image with one shared look.`
          : 'The AI draws the picture; your text and logo are set on it in your brand fonts and colours.'}
      </p>
    </div>
  )
}

function previewLines(type, fields, options) {
  const festival = options.festivals.find((item) => item.value === fields.festival)
  const category = options.announcement_categories.find((item) => item.value === fields.category)
  switch (type) {
    case 'carousel':
      return { headline: fields.topic || 'Your cover headline', body: 'Swipe →', cta: '' }
    case 'festival_creative': {
      const name = fields.festival === 'custom' ? fields.festival_name : festival?.label
      return {
        eyebrow: name ? `Happy ${name}${fields.year ? ` ${fields.year}` : ''}` : 'Happy …',
        headline: fields.headline || 'A warm greeting',
        body: fields.message || '',
      }
    }
    case 'announcement_creative': {
      const label = fields.label || category?.default_label || 'ANNOUNCEMENT'
      return {
        eyebrow: fields.date ? `${label} / ${fields.date}` : label,
        headline: fields.title || 'Announcement title',
        body: fields.description || '',
        cta: fields.cta || '',
      }
    }
    case 'testimonial_creative': {
      const role = [fields.designation, fields.company].filter(Boolean).join(', ')
      return {
        eyebrow: 'What our clients say',
        headline: `“${fields.quote || 'The client’s own words'}”`,
        body: [fields.customer_name, role].filter(Boolean).join(', '),
        stars: Number(fields.rating) || 0,
      }
    }
    default:
      return {
        headline: fields.headline || (type === 'story' ? 'A short, bold message' : 'Your headline'),
        body: fields.supporting_text || '',
        cta: fields.cta || '',
      }
  }
}

function TypeFields({ type, fields, setField, options, photo, setPhoto, slideCount, setSlideCount }) {
  switch (type) {
    case 'post':
      return (
        <>
          <Field label="Topic" required hint="What the post is about - the AI builds the picture and any copy you leave blank from it.">
            <input value={fields.topic || ''} onChange={(e) => setField('topic', e.target.value)} placeholder="e.g. Website development" required />
          </Field>
          <Field label="Headline" hint={EXACT_HINT}>
            <input value={fields.headline || ''} onChange={(e) => setField('headline', e.target.value)} placeholder="Your Website Is Your First Impression." />
          </Field>
          <div className="field-row">
            <Field label="Supporting text">
              <input value={fields.supporting_text || ''} onChange={(e) => setField('supporting_text', e.target.value)} />
            </Field>
            <Field label="Call to action">
              <input value={fields.cta || ''} onChange={(e) => setField('cta', e.target.value)} placeholder="Let's Build Yours" />
            </Field>
          </div>
        </>
      )
    case 'carousel':
      return (
        <>
          <Field label="Topic" required>
            <input value={fields.topic || ''} onChange={(e) => setField('topic', e.target.value)} placeholder="5 signs your business needs a new website" required />
          </Field>
          <div className="field-row">
            <Field label="Number of slides" required>
              <select value={slideCount} onChange={(e) => setSlideCount(Number(e.target.value))}>
                {Array.from({ length: options.carousel_slides.max - options.carousel_slides.min + 1 }, (_, i) => i + options.carousel_slides.min).map((n) => (
                  <option key={n} value={n}>
                    {n} slides
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Content objective">
              <input value={fields.objective || ''} onChange={(e) => setField('objective', e.target.value)} placeholder="Educate, generate leads…" />
            </Field>
          </div>
          <Field
            label="Content outline"
            hint={`Optional. One slide per line as "Headline | supporting text" - ${slideCount - 2} lines fill the middle slides, ${slideCount} lines fill every slide. Leave blank and the AI plans the story.`}
          >
            <textarea rows={4} value={fields.outline || ''} onChange={(e) => setField('outline', e.target.value)} placeholder={'Your website looks outdated | Design affects trust\nVisitors cannot find what they need'} />
          </Field>
          <div className="field-row">
            <Field label="Call to action (last slide)">
              <input value={fields.cta || ''} onChange={(e) => setField('cta', e.target.value)} placeholder="Contact Us" />
            </Field>
            <Field label="Tone">
              <input value={fields.tone || ''} onChange={(e) => setField('tone', e.target.value)} placeholder="Brand tone by default" />
            </Field>
          </div>
        </>
      )
    case 'story':
      return (
        <>
          <Field label="Objective" hint="Shapes both the message and the picture.">
            <select value={fields.objective || ''} onChange={(e) => setField('objective', e.target.value)}>
              <option value="">Choose…</option>
              {options.story_objectives.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Headline" hint={EXACT_HINT}>
            <input value={fields.headline || ''} onChange={(e) => setField('headline', e.target.value)} placeholder="Ready to Grow Your Business?" />
          </Field>
          <div className="field-row">
            <Field label="Supporting message">
              <input value={fields.supporting_text || ''} onChange={(e) => setField('supporting_text', e.target.value)} />
            </Field>
            <Field label="Call to action">
              <input value={fields.cta || ''} onChange={(e) => setField('cta', e.target.value)} placeholder="Let's Talk" />
            </Field>
          </div>
        </>
      )
    case 'festival_creative':
      return (
        <>
          <div className="field-row">
            <Field label="Festival / occasion" required>
              <select value={fields.festival || ''} onChange={(e) => setField('festival', e.target.value)} required>
                <option value="">Choose…</option>
                {options.festivals.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
                <option value="custom">Other occasion…</option>
              </select>
            </Field>
            <Field label="Year">
              <input value={fields.year || ''} onChange={(e) => setField('year', e.target.value)} placeholder="2026" inputMode="numeric" />
            </Field>
          </div>
          {fields.festival === 'custom' && (
            <Field label="Occasion name" required>
              <input value={fields.festival_name || ''} onChange={(e) => setField('festival_name', e.target.value)} required />
            </Field>
          )}
          <Field label="Greeting" hint={EXACT_HINT}>
            <input value={fields.headline || ''} onChange={(e) => setField('headline', e.target.value)} placeholder="Lighting Up New Beginnings" />
          </Field>
          <Field label="Message">
            <input value={fields.message || ''} onChange={(e) => setField('message', e.target.value)} placeholder="Wishing you prosperity, happiness and success." />
          </Field>
          <Field label="Audience">
            <input value={fields.audience || ''} onChange={(e) => setField('audience', e.target.value)} placeholder="Customers, partners, employees…" />
          </Field>
        </>
      )
    case 'announcement_creative':
      return (
        <>
          <div className="field-row">
            <Field label="Category" required>
              <select value={fields.category || ''} onChange={(e) => setField('category', e.target.value)} required>
                <option value="">Choose…</option>
                {options.announcement_categories.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Label">
              <input
                value={fields.label || ''}
                onChange={(e) => setField('label', e.target.value)}
                placeholder={options.announcement_categories.find((c) => c.value === fields.category)?.default_label || 'NEW SERVICE'}
              />
            </Field>
          </div>
          <Field label="Announcement title" required hint="The most prominent text - shown exactly as written.">
            <input value={fields.title || ''} onChange={(e) => setField('title', e.target.value)} placeholder="Introducing Our AI Solutions" required />
          </Field>
          <Field label="Details" hint="Only what you write here is stated - the AI never adds dates, prices or names.">
            <textarea rows={2} value={fields.description || ''} onChange={(e) => setField('description', e.target.value)} />
          </Field>
          <div className="field-row">
            <Field label="Date / time">
              <input value={fields.date || ''} onChange={(e) => setField('date', e.target.value)} placeholder="12 December, 6 PM" />
            </Field>
            <Field label="Call to action">
              <input value={fields.cta || ''} onChange={(e) => setField('cta', e.target.value)} placeholder="Explore Our Solutions" />
            </Field>
          </div>
        </>
      )
    case 'testimonial_creative':
      return (
        <>
          <Field label="Client quote" required hint="The real words of a real client. Nothing on this creative is ever invented.">
            <textarea rows={3} value={fields.quote || ''} onChange={(e) => setField('quote', e.target.value)} required />
          </Field>
          <label className="field-checkbox">
            <input type="checkbox" checked={Boolean(fields.allow_shorten)} onChange={(e) => setField('allow_shorten', e.target.checked)} />
            <span>Let the AI shorten a long quote (only by removing words - the meaning is kept)</span>
          </label>
          <div className="field-row">
            <Field label="Client name">
              <input value={fields.customer_name || ''} onChange={(e) => setField('customer_name', e.target.value)} />
            </Field>
            <Field label="Designation">
              <input value={fields.designation || ''} onChange={(e) => setField('designation', e.target.value)} placeholder="Founder" />
            </Field>
          </div>
          <div className="field-row">
            <Field label="Company">
              <input value={fields.company || ''} onChange={(e) => setField('company', e.target.value)} />
            </Field>
            <Field label="Rating" hint="Stars appear only when you set one.">
              <select value={fields.rating || ''} onChange={(e) => setField('rating', e.target.value)}>
                <option value="">No rating</option>
                {[5, 4, 3, 2, 1].map((n) => (
                  <option key={n} value={n}>
                    {'★'.repeat(n)} ({n})
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <Field label="Client photo" hint="Optional - a real photo you have permission to use (JPG or PNG, up to 5 MB).">
            <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setPhoto(e.target.files?.[0] || null)} />
            {photo && <small className="field-hint-inline">Selected: {photo.name}</small>}
          </Field>
        </>
      )
    default:
      return null
  }
}

/**
 * The creative form: pick a creative type and the form shows only that type's own inputs, its sizes and the design
 * options, with a live layout preview at the real proportions.
 */
export default function CreativeForm({ options, calendarItems, onSubmit, onCancel, submitting, error }) {
  const [common, setCommon] = useState(EMPTY_COMMON)
  const [fieldsByType, setFieldsByType] = useState({})
  const [photo, setPhoto] = useState(null)

  const typeSpec = useMemo(
    () => options.types.find((t) => t.value === common.creative_type) || options.types[0],
    [options, common.creative_type],
  )
  const type = typeSpec.value
  const fields = fieldsByType[type] || {}
  const ratio = typeSpec.aspects.includes(common.aspect_ratio) ? common.aspect_ratio : typeSpec.default_aspect
  const isCarousel = type === 'carousel'
  const images = isCarousel ? common.slide_count : common.variation_count

  function update(key, value) {
    setCommon((prev) => ({ ...prev, [key]: value }))
  }

  function setField(key, value) {
    setFieldsByType((prev) => ({ ...prev, [type]: { ...(prev[type] || {}), [key]: value } }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    const briefFields = Object.fromEntries(
      Object.entries(fields).filter(([key, value]) => typeSpec.fields.includes(key) && value !== '' && value !== false),
    )
    onSubmit(
      {
        ...common,
        aspect_ratio: ratio,
        brief_fields: briefFields,
        content_calendar_item: common.content_calendar_item || null,
        slide_count: isCarousel ? common.slide_count : 0,
        variation_count: isCarousel ? 1 : common.variation_count,
      },
      type === 'testimonial_creative' ? photo : null,
    )
  }

  return (
    <form onSubmit={handleSubmit} className="creative-form">
      {error && <div className="alert alert-error">{error}</div>}

      <fieldset className="cf-section">
        <legend>1. Creative type</legend>
        <div className="cf-types" role="radiogroup" aria-label="Creative type">
          {options.types.map((item) => (
            <button
              key={item.value}
              type="button"
              role="radio"
              aria-checked={type === item.value}
              className={`cf-type ${type === item.value ? 'active' : ''}`}
              onClick={() => update('creative_type', item.value)}
            >
              <span className="cf-type-icon" aria-hidden="true">{ICONS[TYPE_CARDS[item.value]?.icon] || ICONS.image}</span>
              <strong>{item.label.replace(' Creative', '')}</strong>
              <span>{TYPE_CARDS[item.value]?.blurb}</span>
            </button>
          ))}
        </div>
      </fieldset>

      <div className="cf-columns">
        <div className="cf-main">
          <fieldset className="cf-section">
            <legend>2. Content</legend>
            <TypeFields
              type={type}
              fields={fields}
              setField={setField}
              options={options}
              photo={photo}
              setPhoto={setPhoto}
              slideCount={common.slide_count}
              setSlideCount={(n) => update('slide_count', n)}
            />
          </fieldset>

          <fieldset className="cf-section">
            <legend>3. Design</legend>
            <div className="field">
              <span>Design style</span>
              <div className="cf-chips" role="radiogroup" aria-label="Design style">
                <button type="button" className={`cf-chip ${!common.design_style ? 'active' : ''}`} onClick={() => update('design_style', '')}>
                  Brand default
                </button>
                {options.design_styles.map((style) => (
                  <button
                    key={style.value}
                    type="button"
                    className={`cf-chip ${common.design_style === style.value ? 'active' : ''}`}
                    onClick={() => update('design_style', style.value)}
                  >
                    {style.label}
                  </button>
                ))}
              </div>
              <small className="field-hint-inline">Shapes layout, typography, lighting and mood - your brand colours stay.</small>
            </div>
            {typeSpec.aspects.length > 1 && (
              <div className="field">
                <span>Size</span>
                <div className="segmented" role="radiogroup" aria-label="Size">
                  {options.aspect_ratios.filter((item) => typeSpec.aspects.includes(item.value)).map((item) => (
                    <button key={item.value} type="button" className={ratio === item.value ? 'active' : ''} onClick={() => update('aspect_ratio', item.value)}>
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {!isCarousel && (
              <div className="field">
                <span>Variations</span>
                <div className="segmented" role="radiogroup" aria-label="Variations">
                  {[1, 2, 3].map((n) => (
                    <button key={n} type="button" className={common.variation_count === n ? 'active' : ''} onClick={() => update('variation_count', n)}>
                      {n}
                    </button>
                  ))}
                </div>
                <small className="field-hint-inline">Each variation is composed differently. Use 1 while testing a brief.</small>
              </div>
            )}
            {!typeSpec.force_overlay && (
              <label className="field-checkbox">
                <input type="checkbox" checked={common.include_text_overlay} onChange={(e) => update('include_text_overlay', e.target.checked)} />
                <span>Set the text on the image (untick for a clean photo with only the logo)</span>
              </label>
            )}
          </fieldset>

          <fieldset className="cf-section">
            <legend>4. Publishing details</legend>
            <div className="field-row">
              <Field label="Platform">
                <select value={common.platform} onChange={(e) => update('platform', e.target.value)}>
                  {PLATFORMS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Content calendar item">
                <select value={common.content_calendar_item} onChange={(e) => update('content_calendar_item', e.target.value)}>
                  <option value="">None - add it to the calendar for approval</option>
                  {calendarItems.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.topic} ({item.scheduled_date})
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="Visual direction" hint="Optional notes for the picture - setting, props, mood.">
              <textarea rows={2} value={common.prompt_brief} onChange={(e) => update('prompt_brief', e.target.value)} />
            </Field>
          </fieldset>
        </div>

        <aside className="cf-side">
          <LayoutPreview type={type} ratio={ratio} fields={fields} slideCount={common.slide_count} options={options} />
        </aside>
      </div>

      <div className="modal-actions cf-actions">
        <span className="cf-cost">
          Uses {images} AI image {images === 1 ? 'credit' : 'credits'}
          {isCarousel ? ` (one per slide)` : ''}
        </span>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? 'Starting…' : isCarousel ? `Generate ${common.slide_count} slides` : 'Generate'}
        </button>
      </div>
    </form>
  )
}
