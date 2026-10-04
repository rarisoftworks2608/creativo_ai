import apiClient from './client'

export async function listPlans(params = {}) {
  const response = await apiClient.get('/subscriptions/plans/', { params })
  return response.data
}

export async function createPlan(payload) {
  const response = await apiClient.post('/subscriptions/plans/', payload)
  return response.data
}

export async function updatePlan(id, payload) {
  const response = await apiClient.patch(`/subscriptions/plans/${id}/`, payload)
  return response.data
}

export async function deletePlan(id) {
  const response = await apiClient.delete(`/subscriptions/plans/${id}/`)
  return response.data
}

export async function listSubscriptions(params = {}) {
  const response = await apiClient.get('/subscriptions/', { params })
  return response.data
}

export async function createSubscription(payload) {
  const response = await apiClient.post('/subscriptions/', payload)
  return response.data
}

export async function updateSubscription(id, payload) {
  const response = await apiClient.patch(`/subscriptions/${id}/`, payload)
  return response.data
}

export async function getUsageOverview() {
  const response = await apiClient.get('/subscriptions/usage-overview/')
  return response.data
}

export async function getCompanySubscription(companyId) {
  const response = await apiClient.get(`/companies/${companyId}/subscription/`)
  return response.data
}

export async function recalculateStorage(companyId) {
  const response = await apiClient.post(`/companies/${companyId}/subscription/recalculate-storage/`)
  return response.data
}

export async function listBillingRecords(companyId) {
  const response = await apiClient.get(`/companies/${companyId}/subscription/billing/`)
  return response.data
}

function toFormData(payload) {
  const formData = new FormData()
  Object.entries(payload).forEach(([key, value]) => {
    if (value === null || value === undefined || value === '') return
    formData.append(key, value)
  })
  return formData
}

export async function createBillingRecord(companyId, payload) {
  const hasFile = payload.invoice_file instanceof File
  const response = await apiClient.post(
    `/companies/${companyId}/subscription/billing/`,
    hasFile ? toFormData(payload) : payload,
    hasFile ? { headers: { 'Content-Type': 'multipart/form-data' } } : undefined,
  )
  return response.data
}

export async function updateBillingRecord(companyId, recordId, payload) {
  const hasFile = payload.invoice_file instanceof File
  const body = { ...payload }
  if (!hasFile) delete body.invoice_file
  const response = await apiClient.patch(
    `/companies/${companyId}/subscription/billing/${recordId}/`,
    hasFile ? toFormData(body) : body,
    hasFile ? { headers: { 'Content-Type': 'multipart/form-data' } } : undefined,
  )
  return response.data
}

export async function deleteBillingRecord(companyId, recordId) {
  await apiClient.delete(`/companies/${companyId}/subscription/billing/${recordId}/`)
}
