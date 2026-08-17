import { useState } from 'react'

export default function TagsInput({ value = [], onChange, placeholder }) {
  const [draft, setDraft] = useState('')

  function commitDraft() {
    const tag = draft.trim()
    if (tag && !value.includes(tag)) {
      onChange([...value, tag])
    }
    setDraft('')
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault()
      commitDraft()
    } else if (event.key === 'Backspace' && !draft && value.length > 0) {
      onChange(value.slice(0, -1))
    }
  }

  function removeTag(tag) {
    onChange(value.filter((item) => item !== tag))
  }

  return (
    <div className="tags-input" onClick={(e) => e.currentTarget.querySelector('input')?.focus()}>
      {value.map((tag) => (
        <span key={tag} className="tag-chip">
          {tag}
          <button type="button" onClick={() => removeTag(tag)} aria-label={`Remove ${tag}`}>
            ×
          </button>
        </span>
      ))}
      <input
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={commitDraft}
        placeholder={value.length === 0 ? placeholder : ''}
      />
    </div>
  )
}
