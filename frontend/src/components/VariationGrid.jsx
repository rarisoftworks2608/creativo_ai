import { useEffect, useState } from 'react'

// Click-to-enlarge viewer: shows the whole creative (the grid thumbnail is small, and a
// creative's brand footer with the logo/headline/CTA must be visible in full).
function ImageLightbox({ variation, onClose }) {
  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="lightbox" onClick={onClose} role="dialog" aria-modal="true" aria-label={`Variation ${variation.variation_number}`}>
      <button type="button" className="lightbox-close" onClick={onClose} aria-label="Close">
        ×
      </button>
      <img src={variation.image} alt={`Variation ${variation.variation_number}`} className="lightbox-image" onClick={(event) => event.stopPropagation()} />
      <a
        className="lightbox-open"
        href={variation.image}
        target="_blank"
        rel="noreferrer"
        onClick={(event) => event.stopPropagation()}
      >
        Open original in new tab
      </a>
    </div>
  )
}

export default function VariationGrid({ variations, onSelect, selecting }) {
  const [preview, setPreview] = useState(null)

  return (
    <div className="variation-grid">
      {preview && <ImageLightbox variation={preview} onClose={() => setPreview(null)} />}
      {variations.map((variation) => (
        <div className={`variation-card ${variation.is_selected ? 'variation-card-selected' : ''}`} key={variation.id}>
          <img
            src={variation.image}
            alt={`Variation ${variation.variation_number}`}
            className="variation-image variation-image-zoom"
            title="Click to view full size"
            onClick={() => setPreview(variation)}
          />
          <div className="variation-body">
            <div className="variation-label">
              Variation {variation.variation_number}
              {variation.is_selected && <span className="variation-selected-tag">Selected</span>}
            </div>
            {variation.eyebrow && <div className="variation-eyebrow">{variation.eyebrow}</div>}
            {variation.headline && <div className="variation-headline">{variation.headline}</div>}
            {variation.description && <p className="variation-caption">{variation.description}</p>}
            {variation.caption && <p className="variation-caption">{variation.caption}</p>}
            {variation.cta && (
              <p className="variation-caption">
                <strong>CTA:</strong> {variation.cta}
              </p>
            )}
            {variation.hashtags.length > 0 && (
              <div className="tag-list">
                {variation.hashtags.map((tag) => (
                  <span key={tag} className="tag-chip tag-chip-static">
                    {tag}
                  </span>
                ))}
              </div>
            )}
            {onSelect && (
              <button
                type="button"
                className="btn btn-ghost btn-block"
                disabled={variation.is_selected || selecting === variation.id}
                onClick={() => onSelect(variation.id)}
              >
                {variation.is_selected ? 'Selected' : 'Select this version'}
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
