const HEX_RE = /^#(?:[0-9a-fA-F]{3}){1,2}$/

export default function ColorPaletteInput({ value = [], onChange }) {
  function updateRow(index, key, fieldValue) {
    const next = value.map((row, i) => (i === index ? { ...row, [key]: fieldValue } : row))
    onChange(next)
  }

  function addRow() {
    onChange([...value, { name: '', hex: '#000000' }])
  }

  function removeRow(index) {
    onChange(value.filter((_, i) => i !== index))
  }

  return (
    <div className="color-palette">
      {value.map((row, index) => {
        const isValidHex = HEX_RE.test(row.hex || '')
        return (
          <div className="color-palette-row" key={index}>
            <input
              type="color"
              className="color-swatch-input"
              value={isValidHex ? row.hex : '#000000'}
              onChange={(e) => updateRow(index, 'hex', e.target.value)}
            />
            <input
              value={row.name || ''}
              placeholder="Name, e.g. Primary"
              onChange={(e) => updateRow(index, 'name', e.target.value)}
            />
            <input
              value={row.hex || ''}
              placeholder="#AA3BFF"
              className={isValidHex ? '' : 'input-invalid'}
              onChange={(e) => updateRow(index, 'hex', e.target.value)}
            />
            <button type="button" className="object-list-remove" onClick={() => removeRow(index)} aria-label="Remove">
              ×
            </button>
          </div>
        )
      })}
      <button type="button" className="btn btn-ghost btn-block" onClick={addRow}>
        + Add color
      </button>
    </div>
  )
}
