import apiClient from './client'

export async function listSocialAccounts(companyId) {
  const response = await apiClient.get(`/companies/${companyId}/social-accounts/accounts/`)
  return response.data
}

export async function connectSocialAccount(companyId, payload) {
  const response = await apiClient.post(`/companies/${companyId}/social-accounts/accounts/`, payload)
  return response.data
}

export async function updateSocialAccount(companyId, accountId, payload) {
  const response = await apiClient.patch(`/companies/${companyId}/social-accounts/accounts/${accountId}/`, payload)
  return response.data
}

export async function disconnectSocialAccount(companyId, accountId) {
  const response = await apiClient.post(`/companies/${companyId}/social-accounts/accounts/${accountId}/disconnect/`)
  return response.data
}
