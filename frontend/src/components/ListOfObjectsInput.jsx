// Generic editor for a list of small objects, e.g. fonts ({name, usage}) or
// customer personas ({name, summary}) — same repeated-row UI, different fields.
export default function ListOfObjectsInput({ value = [], onChange, fields, addLabel = '+ Add' }) {
  function updateRow(index, key, fieldValue) {
    const next = value.map((row, i) => (i === index ? { ...row, [key]: fieldValue } : row))
    onChange(next)
  }

  function addRow() {
    const blank = Object.fromEntries(fields.map((f) => [f.key, '']))
    onChange([...value, blank])
  }

  function removeRow(index) {
    onChange(value.filter((_, i) => i !== index))
  }

  return (
    <div className="object-list">
      {value.map((row, index) => (
        <div className="object-list-row" key={index}>
          {fields.map((f) => (
            <input
              key={f.key}
              value={row[f.key] || ''}
              placeholder={f.placeholder}
              onChange={(e) => updateRow(index, f.key, e.target.value)}
            />
          ))}
          <button type="button" className="object-list-remove" onClick={() => removeRow(index)} aria-label="Remove">
            ×
          </button>
        </div>
      ))}
      <button type="button" className="btn btn-ghost btn-block" onClick={addRow}>
        {addLabel}
      </button>
    </div>
  )
}
