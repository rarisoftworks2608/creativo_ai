import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { listMediaLibrary } from '../api/mediaLibrary'
import { deleteBrandAsset, renameBrandAsset } from '../api/brand'
import { getCompany } from '../api/companies'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import Modal from '../components/Modal'

const SECTIONS = [
  {
    source: 'brand_asset',
    title: 'Brand Assets',
    description: 'Uploaded manually on the Brand page (logos, reference images, documents). Renamable and deletable here.',
  },
  {
    source: 'creative_variation',
    title: 'Generated Creatives',
    description: 'Images generated on the AI Creative Generation page - shown to the client for approval before publishing. Reference only; manage them from that page.',
  },
  {
    source: 'video',
    title: 'Generated Videos',
    description: 'Videos generated on the AI Video Generation page - shown to the client for approval before publishing. Reference only; manage them from that page.',
  },
]

export default function MediaLibraryPage() {
  const { id: companyId } = useParams()
  const { isAdmin } = useAuth()

  const [company, setCompany] = useState(null)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [search, setSearch] = useState('')

  const [previewItem, setPreviewItem] = useState(null)
  const [renamingId, setRenamingId] = useState(null)
  const [renameValue, setRenameValue] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [downloadingId, setDownloadingId] = useState(null)

  const load = useCallback(async () => {
    if (!isAdmin) {
      setLoading(false)
      return
    }
    setLoading(true)
    setLoadError('')
    try {
      const [companyData, mediaData] = await Promise.all([
        getCompany(companyId),
        listMediaLibrary(companyId, { search: search || undefined }),
      ])
      setCompany(companyData)
      setItems(mediaData.results)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load the media library.'))
    } finally {
      setLoading(false)
    }
  }, [companyId, isAdmin, search])

  useEffect(() => {
    const timeout = setTimeout(load, 250)
    return () => clearTimeout(timeout)
  }, [load])

  function startRename(item) {
    setRenamingId(item.id)
    setRenameValue(item.name)
  }

  async function handleSaveRename(item) {
    if (!renameValue.trim()) return
    setBusyId(item.id)
    try {
      const updated = await renameBrandAsset(companyId, item.source_id, renameValue.trim())
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, name: updated.name } : i)))
      setRenamingId(null)
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not rename this file.'))
    } finally {
      setBusyId(null)
    }
  }

  async function handleDelete(item) {
    if (!window.confirm(`Delete "${item.name}"? This cannot be undone.`)) return
    setBusyId(item.id)
    try {
      await deleteBrandAsset(companyId, item.source_id)
      setItems((prev) => prev.filter((i) => i.id !== item.id))
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not delete this file.'))
    } finally {
      setBusyId(null)
    }
  }

  async function handleDownload(item) {
    // A plain <a href> to the backend's media URL just opens the file in a new
    // tab instead of downloading it, since it's a different origin than the
    // frontend (browsers only honor the `download` attribute same-origin).
    // Fetching the bytes and downloading via a blob: URL works regardless of origin.
    setDownloadingId(item.id)
    try {
      const response = await fetch(item.url)
      if (!response.ok) throw new Error('Download failed.')
      const blob = await response.blob()
      const blobUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = blobUrl
      link.download = item.name || 'file'
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(blobUrl)
    } catch {
      setLoadError(`Could not download "${item.name}".`)
    } finally {
      setDownloadingId(null)
    }
  }

  if (!isAdmin) {
    return <div className="alert alert-error">The media library is only available to admins.</div>
  }
  if (loading && !company) return <div className="page-loading">Loading…</div>
  if (loadError && !company) return <div className="alert alert-error">{loadError}</div>
  if (!company) return null

  return (
    <div>
      <Link to={`/companies/${companyId}`} className="back-link">
        ← Back to {company.name}
      </Link>

      <div className="page-header">
        <div>
          <h1>Media Library</h1>
          <p className="page-subtitle">{company.name} · {items.length} file{items.length === 1 ? '' : 's'}</p>
        </div>
      </div>

      <div className="toolbar">
        <input
          type="search"
          placeholder="Search by name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="search-input"
        />
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      {items.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <p>No media found.</p>
          </div>
        </div>
      ) : (
        SECTIONS.map((section) => {
          const sectionItems = items.filter((item) => item.source === section.source)
          if (sectionItems.length === 0) return null
          return (
            <div key={section.source} style={{ marginBottom: 32 }}>
              <h2 className="dashboard-section-title" style={{ marginBottom: 4 }}>
                {section.title} ({sectionItems.length})
              </h2>
              <p className="page-subtitle" style={{ marginBottom: 12 }}>{section.description}</p>
              <div className="asset-grid">
                {sectionItems.map((item) => (
                  <div className="asset-card" key={item.id}>
                    <button type="button" className="asset-thumb" onClick={() => setPreviewItem(item)}>
                      {item.type === 'video' ? (
                        item.thumbnail_url ? <img src={item.thumbnail_url} alt={item.name} /> : <span className="asset-thumb-icon">🎬</span>
                      ) : item.thumbnail_url ? (
                        <img src={item.thumbnail_url} alt={item.name} />
                      ) : (
                        <span className="asset-thumb-icon">📄</span>
                      )}
                    </button>
                    <div className="asset-meta">
                      {renamingId === item.id ? (
                        <input
                          autoFocus
                          value={renameValue}
                          disabled={busyId === item.id}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSaveRename(item)
                            if (e.key === 'Escape') setRenamingId(null)
                          }}
                          onBlur={() => handleSaveRename(item)}
                        />
                      ) : (
                        <div className="asset-name" title={item.name} onClick={() => item.renamable && startRename(item)}>
                          {item.name}
                        </div>
                      )}
                      <div className="asset-category">{item.category}</div>
                    </div>
                    <div className="table-actions">
                      <button
                        type="button"
                        className="btn-link"
                        disabled={downloadingId === item.id}
                        onClick={() => handleDownload(item)}
                      >
                        {downloadingId === item.id ? 'Downloading…' : 'Download'}
                      </button>
                      {item.renamable && (
                        <button type="button" className="btn-link" onClick={() => startRename(item)}>
                          Rename
                        </button>
                      )}
                      {item.deletable && (
                        <button
                          type="button"
                          className="btn-link btn-link-danger"
                          disabled={busyId === item.id}
                          onClick={() => handleDelete(item)}
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })
      )}

      {previewItem && (
        <Modal title={previewItem.name} onClose={() => setPreviewItem(null)} width={640}>
          {previewItem.type === 'video' ? (
            <video controls src={previewItem.url} poster={previewItem.thumbnail_url || undefined} style={{ width: '100%' }} />
          ) : previewItem.type === 'image' ? (
            <img src={previewItem.url} alt={previewItem.name} style={{ width: '100%' }} />
          ) : (
            <p>
              <a href={previewItem.url} target="_blank" rel="noreferrer">
                Open file
              </a>
            </p>
          )}
        </Modal>
      )}
    </div>
  )
}
