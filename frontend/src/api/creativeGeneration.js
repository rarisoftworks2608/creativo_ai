import apiClient from './client'
import { downloadFile } from '../utils/download'

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

const base = (companyId) => `/companies/${companyId}/creative-generation`

// The inputs, sizes and styles each creative type offers - served by the backend so both sides agree.
export async function getCreativeOptions(companyId) {
  const response = await apiClient.get(`${base(companyId)}/options/`)
  return response.data
}

// Sends multipart only when a file is attached (a testimonial's client photo); brief_fields then travels as JSON text.
export async function createCreative(companyId, payload, photoFile, referenceFile) {
  if (!photoFile && !referenceFile) return createGenerationRequest(companyId, payload)
  const form = new FormData()
  Object.entries(payload).forEach(([key, value]) => {
    if (value === null || value === undefined) return
    form.append(key, typeof value === 'object' ? JSON.stringify(value) : value)
  })
  if (photoFile) form.append('customer_photo', photoFile)
  if (referenceFile) form.append('reference_image', referenceFile)
  const response = await apiClient.post(`${base(companyId)}/requests/`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

// Re-renders the edited text onto the kept picture - no AI call.
export async function editVariation(companyId, requestId, variationId, payload) {
  const response = await apiClient.patch(`${base(companyId)}/requests/${requestId}/variations/${variationId}/`, payload)
  return response.data
}

// A new picture for one variation or one carousel slide (one image credit), keeping its text.
export async function regenerateVariation(companyId, requestId, variationId) {
  const response = await apiClient.post(`${base(companyId)}/requests/${requestId}/variations/${variationId}/regenerate/`)
  return response.data
}

// Every image of a creative as a zip (authenticated, so fetched as a blob and saved by the browser).
export function downloadCreativeZip(companyId, requestId) {
  return downloadFile(`${base(companyId)}/requests/${requestId}/download/`, `creative-${requestId}.zip`)
}
