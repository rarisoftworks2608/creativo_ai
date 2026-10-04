import apiClient from './client'

export async function getHealthDetails() {
  const response = await apiClient.get('/health/details/')
  return response.data
}

export async function listMusicTracks(params = {}) {
  const response = await apiClient.get('/music-library/', { params })
  return response.data
}

export async function uploadMusicTrack({ name, mood, license_note, file }) {
  const formData = new FormData()
  formData.append('name', name)
  formData.append('mood', mood)
  if (license_note) formData.append('license_note', license_note)
  formData.append('file', file)
  const response = await apiClient.post('/music-library/', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
  return response.data
}

export async function updateMusicTrack(id, payload) {
  const response = await apiClient.patch(`/music-library/${id}/`, payload)
  return response.data
}

export async function deleteMusicTrack(id) {
  await apiClient.delete(`/music-library/${id}/`)
}
