import { useRef, useState } from 'react'

export default function BrandImageSlot({ label, hint, imageUrl, onUpload, onRemove }) {
  const inputRef = useRef(null)
  const [busy, setBusy] = useState(false)

  async function handleFileChange(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setBusy(true)
    try {
      await onUpload(file)
    } finally {
      setBusy(false)
    }
  }

  async function handleRemove() {
    setBusy(true)
    try {
      await onRemove()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="image-slot">
      <div className="image-slot-preview">
        {imageUrl ? <img src={imageUrl} alt={label} /> : <span className="image-slot-placeholder">No {label.toLowerCase()}</span>}
      </div>
      <div className="image-slot-body">
        <div className="image-slot-label">{label}</div>
        {hint && <div className="image-slot-hint">{hint}</div>}
        <div className="image-slot-actions">
          <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => inputRef.current?.click()}>
            {busy ? 'Working…' : imageUrl ? 'Replace' : 'Upload'}
          </button>
          {imageUrl && (
            <button type="button" className="btn-link btn-link-danger" disabled={busy} onClick={handleRemove}>
              Remove
            </button>
          )}
          <input ref={inputRef} type="file" accept="image/*" hidden onChange={handleFileChange} />
        </div>
      </div>
    </div>
  )
}
