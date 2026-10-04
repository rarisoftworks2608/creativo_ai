import { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { deleteMusicTrack, listMusicTracks, updateMusicTrack, uploadMusicTrack } from '../api/system'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'

const MOODS = [
  ['upbeat', 'Upbeat'],
  ['calm', 'Calm'],
  ['corporate', 'Corporate'],
  ['cinematic', 'Cinematic'],
  ['inspirational', 'Inspirational'],
  ['festive', 'Festive'],
  ['other', 'Other'],
]

export default function MusicLibraryPage() {
  const { isAdmin } = useAuth()
  const [tracks, setTracks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ name: '', mood: 'upbeat', license_note: '', file: null })
  const [uploading, setUploading] = useState(false)

  const load = useCallback(async () => {
    try {
      setTracks(await listMusicTracks())
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load the music library.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isAdmin) load()
  }, [isAdmin, load])

  if (!isAdmin) return <Navigate to="/client" replace />

  async function upload(event) {
    event.preventDefault()
    setUploading(true)
    setError('')
    try {
      await uploadMusicTrack(form)
      setForm({ name: '', mood: 'upbeat', license_note: '', file: null })
      event.target.reset()
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not upload the track.'))
    } finally {
      setUploading(false)
    }
  }

  async function toggle(track) {
    try {
      await updateMusicTrack(track.id, { is_active: !track.is_active })
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not update the track.'))
    }
  }

  async function remove(track) {
    if (!window.confirm(`Delete "${track.name}"?`)) return
    try {
      await deleteMusicTrack(track.id)
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not delete the track.'))
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Music library</h1>
          <p className="page-subtitle">
            Background music for AI videos. Only upload tracks you have commercial rights to (e.g. YouTube Audio Library, Pixabay
            Music, or licensed stock).
          </p>
        </div>
      </div>

      <form className="card report-builder" onSubmit={upload}>
        <label className="field">
          <span>Track name *</span>
          <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
        </label>
        <label className="field">
          <span>Mood</span>
          <select value={form.mood} onChange={(e) => setForm((f) => ({ ...f, mood: e.target.value }))}>
            {MOODS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Source / license</span>
          <input value={form.license_note} onChange={(e) => setForm((f) => ({ ...f, license_note: e.target.value }))} placeholder="e.g. Pixabay license" />
        </label>
        <label className="field">
          <span>Audio file *</span>
          <input type="file" accept=".mp3,.m4a,.aac,.wav,.ogg,audio/*" onChange={(e) => setForm((f) => ({ ...f, file: e.target.files?.[0] || null }))} required />
        </label>
        <button type="submit" className="btn btn-primary" disabled={uploading}>
          {uploading ? 'Uploading…' : 'Upload'}
        </button>
      </form>

      {error && <div className="alert alert-error">{error}</div>}
      {loading ? (
        <div className="page-loading">Loading…</div>
      ) : tracks.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <p>No music yet. Videos with “Background music” on will render without music until a track is added.</p>
          </div>
        </div>
      ) : (
        <div className="music-list">
          {tracks.map((track) => (
            <div className={`card music-row ${track.is_active ? '' : 'plan-tile-inactive'}`} key={track.id}>
              <div className="music-info">
                <strong>{track.name}</strong>
                <span className="page-subtitle">
                  {track.mood_display}
                  {track.license_note ? ` · ${track.license_note}` : ''}
                  {track.is_active ? '' : ' · inactive'}
                </span>
              </div>
              <audio controls src={track.file} preload="none" className="music-player" />
              <div className="music-actions">
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => toggle(track)}>
                  {track.is_active ? 'Deactivate' : 'Activate'}
                </button>
                <button type="button" className="btn-link btn-link-danger" onClick={() => remove(track)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
