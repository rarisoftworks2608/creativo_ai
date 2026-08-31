export default function VariationGrid({ variations, onSelect, selecting }) {
  return (
    <div className="variation-grid">
      {variations.map((variation) => (
        <div className={`variation-card ${variation.is_selected ? 'variation-card-selected' : ''}`} key={variation.id}>
          <img src={variation.image} alt={`Variation ${variation.variation_number}`} className="variation-image" />
          <div className="variation-body">
            <div className="variation-label">
              Variation {variation.variation_number}
              {variation.is_selected && <span className="variation-selected-tag">Selected</span>}
            </div>
            {variation.headline && <div className="variation-headline">{variation.headline}</div>}
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
