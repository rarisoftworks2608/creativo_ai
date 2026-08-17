import apiClient from './client'

export async function listCompanies({ search, status } = {}) {
  const params = {}
  if (search) params.search = search
  if (status) params.status = status
  const response = await apiClient.get('/companies/', { params })
  return response.data
}

export async function getCompany(id) {
  const response = await apiClient.get(`/companies/${id}/`)
  return response.data
}

export async function createCompany(payload) {
  const response = await apiClient.post('/companies/', payload)
  return response.data
}

export async function updateCompany(id, payload) {
  const response = await apiClient.patch(`/companies/${id}/`, payload)
  return response.data
}

export async function setCompanyStatus(id, action) {
  const response = await apiClient.post(`/companies/${id}/${action}/`)
  return response.data
}

export async function listCompanyClients(companyId) {
  const response = await apiClient.get(`/companies/${companyId}/clients/`)
  return response.data
}

export async function addCompanyClient(companyId, payload) {
  const response = await apiClient.post(`/companies/${companyId}/clients/`, payload)
  return response.data
}

export async function updateCompanyClient(companyId, profileId, payload) {
  const response = await apiClient.patch(`/companies/${companyId}/clients/${profileId}/`, payload)
  return response.data
}

export async function removeCompanyClient(companyId, profileId) {
  await apiClient.delete(`/companies/${companyId}/clients/${profileId}/`)
}
