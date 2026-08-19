import apiClient from './client'

export async function getBrandProfile(companyId) {
  const response = await apiClient.get(`/companies/${companyId}/brand/`)
  return response.data
}

export async function updateBrandProfile(companyId, payload) {
  const response = await apiClient.patch(`/companies/${companyId}/brand/`, payload)
  return response.data
}

export async function uploadBrandImage(companyId, slot, file) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiClient.post(`/companies/${companyId}/brand/${slot}/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function removeBrandImage(companyId, slot) {
  const response = await apiClient.delete(`/companies/${companyId}/brand/${slot}/`)
  return response.data
}

export async function listBrandAssets(companyId, { category } = {}) {
  const params = {}
  if (category) params.category = category
  const response = await apiClient.get(`/companies/${companyId}/brand/assets/`, { params })
  return response.data
}

export async function uploadBrandAsset(companyId, { file, category, name }) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('category', category)
  if (name) formData.append('name', name)
  const response = await apiClient.post(`/companies/${companyId}/brand/assets/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function deleteBrandAsset(companyId, assetId) {
  await apiClient.delete(`/companies/${companyId}/brand/assets/${assetId}/`)
}
