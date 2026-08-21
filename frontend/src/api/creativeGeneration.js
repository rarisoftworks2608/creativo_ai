import apiClient from './client'

export async function listGenerationRequests(companyId, { status, creativeType } = {}) {
  const params = {}
  if (status) params.status = status
  if (creativeType) params.creative_type = creativeType
  const response = await apiClient.get(`/companies/${companyId}/creative-generation/requests/`, { params })
  return response.data
}

export async function createGenerationRequest(companyId, payload) {
  const response = await apiClient.post(`/companies/${companyId}/creative-generation/requests/`, payload)
  return response.data
}

export async function getGenerationRequest(companyId, requestId) {
  const response = await apiClient.get(`/companies/${companyId}/creative-generation/requests/${requestId}/`)
  return response.data
}

export async function retryGenerationRequest(companyId, requestId) {
  const response = await apiClient.post(`/companies/${companyId}/creative-generation/requests/${requestId}/retry/`)
  return response.data
}

export async function selectVariation(companyId, requestId, variationId) {
  const response = await apiClient.post(
    `/companies/${companyId}/creative-generation/requests/${requestId}/variations/${variationId}/select/`,
  )
  return response.data
}
