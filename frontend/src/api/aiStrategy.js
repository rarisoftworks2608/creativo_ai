import apiClient from './client'

export async function getBrandContext(companyId) {
  const response = await apiClient.get(`/companies/${companyId}/ai-strategy/brand-context/`)
  return response.data
}

export async function generateBrandContext(companyId) {
  const response = await apiClient.post(`/companies/${companyId}/ai-strategy/brand-context/generate/`)
  return response.data
}

export async function listStrategyOutputs(companyId, { kind } = {}) {
  const params = {}
  if (kind) params.kind = kind
  const response = await apiClient.get(`/companies/${companyId}/ai-strategy/outputs/`, { params })
  return response.data
}

export async function generateStrategyOutput(companyId, kind, notes = '') {
  const response = await apiClient.post(`/companies/${companyId}/ai-strategy/outputs/generate/${kind}/`, { notes })
  return response.data
}
