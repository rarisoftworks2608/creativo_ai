import apiClient from './client'

const base = (companyId) => `/companies/${companyId}/whatsapp`

export async function getWhatsAppConfig(companyId) {
  const response = await apiClient.get(`${base(companyId)}/config/`)
  return response.data
}

export async function updateWhatsAppConfig(companyId, payload) {
  const response = await apiClient.patch(`${base(companyId)}/config/`, payload)
  return response.data
}

export async function createWhatsAppGroup(companyId, payload) {
  const response = await apiClient.post(`${base(companyId)}/group/`, payload)
  return response.data
}

export async function deactivateWhatsAppGroup(companyId) {
  const response = await apiClient.delete(`${base(companyId)}/group/`)
  return response.data
}

export async function listWhatsAppMessages(companyId, params = {}) {
  const response = await apiClient.get(`${base(companyId)}/messages/`, { params })
  return response.data
}

export async function resendWhatsAppMessage(companyId, messageId) {
  const response = await apiClient.post(`${base(companyId)}/messages/${messageId}/resend/`)
  return response.data
}

export async function sendWhatsAppTest(companyId, phone) {
  const response = await apiClient.post(`${base(companyId)}/test-message/`, { phone })
  return response.data
}

export async function getWhatsAppStatus() {
  const response = await apiClient.get('/whatsapp/status/')
  return response.data
}

export async function listWhatsAppTemplates() {
  const response = await apiClient.get('/whatsapp/templates/')
  return response.data
}

export async function createWhatsAppTemplate(payload) {
  const response = await apiClient.post('/whatsapp/templates/', payload)
  return response.data
}

export async function updateWhatsAppTemplate(id, payload) {
  const response = await apiClient.patch(`/whatsapp/templates/${id}/`, payload)
  return response.data
}

export async function deleteWhatsAppTemplate(id) {
  await apiClient.delete(`/whatsapp/templates/${id}/`)
}

export async function syncWhatsAppTemplates() {
  const response = await apiClient.post('/whatsapp/templates/sync/')
  return response.data
}
