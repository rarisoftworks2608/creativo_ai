import apiClient from './client'

export async function listPromptTemplates(params = {}) {
  const response = await apiClient.get('/prompt-templates/', { params })
  return response.data
}

export async function createPromptTemplate(payload) {
  const response = await apiClient.post('/prompt-templates/', payload)
  return response.data
}

export async function deletePromptTemplate(id) {
  await apiClient.delete(`/prompt-templates/${id}/`)
}

export async function fetchPromptTemplateHistory(slug) {
  const response = await apiClient.get(`/prompt-templates/history/${slug}/`)
  return response.data
}

export async function createPromptTemplateVersion(id, payload) {
  const response = await apiClient.post(`/prompt-templates/${id}/new-version/`, payload)
  return response.data
}

export async function activatePromptTemplate(id) {
  const response = await apiClient.post(`/prompt-templates/${id}/activate/`)
  return response.data
}

export async function deactivatePromptTemplate(id) {
  const response = await apiClient.post(`/prompt-templates/${id}/deactivate/`)
  return response.data
}
