import apiClient from './client'

const base = (companyId) => `/companies/${companyId}/publishing`

export async function listPublishJobs(companyId, params = {}) {
  const response = await apiClient.get(`${base(companyId)}/jobs/`, { params })
  return response.data
}

export async function createPublishJobs(companyId, payload) {
  const response = await apiClient.post(`${base(companyId)}/jobs/`, payload)
  return response.data
}

export async function updatePublishJob(companyId, jobId, payload) {
  const response = await apiClient.patch(`${base(companyId)}/jobs/${jobId}/`, payload)
  return response.data
}

export async function cancelPublishJob(companyId, jobId) {
  const response = await apiClient.post(`${base(companyId)}/jobs/${jobId}/cancel/`)
  return response.data
}

export async function retryPublishJob(companyId, jobId) {
  const response = await apiClient.post(`${base(companyId)}/jobs/${jobId}/retry/`)
  return response.data
}

export async function publishJobNow(companyId, jobId) {
  const response = await apiClient.post(`${base(companyId)}/jobs/${jobId}/publish-now/`)
  return response.data
}

export async function getReadyToPublish(companyId) {
  const response = await apiClient.get(`${base(companyId)}/ready/`)
  return response.data
}

export async function getPublishPreview(companyId, itemId) {
  const response = await apiClient.get(`${base(companyId)}/preview/${itemId}/`)
  return response.data
}

export async function getPublishingStats(companyId) {
  const response = await apiClient.get(`${base(companyId)}/stats/`)
  return response.data
}

export async function listGlobalPublishQueue(params = {}) {
  const response = await apiClient.get('/publishing/queue/', { params })
  return response.data
}
