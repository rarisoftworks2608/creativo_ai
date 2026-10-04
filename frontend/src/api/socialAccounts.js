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

export async function testSocialAccountConnection(companyId, accountId) {
  const response = await apiClient.post(`/companies/${companyId}/social-accounts/accounts/${accountId}/test-connection/`)
  return response.data
}

export async function refreshSocialToken(companyId, accountId) {
  const response = await apiClient.post(`/companies/${companyId}/social-accounts/accounts/${accountId}/refresh-token/`)
  return response.data
}

export async function getOAuthStatus(companyId) {
  const response = await apiClient.get(`/companies/${companyId}/social-accounts/oauth/status/`)
  return response.data
}

export async function startOAuth(companyId, provider) {
  const response = await apiClient.get(`/companies/${companyId}/social-accounts/oauth/${provider}/start/`)
  return response.data
}

export async function completeOAuth(companyId, provider, code, state) {
  const response = await apiClient.post(`/companies/${companyId}/social-accounts/oauth/${provider}/complete/`, { code, state })
  return response.data
}

export async function connectOAuthAccounts(companyId, sessionId, keys) {
  const response = await apiClient.post(`/companies/${companyId}/social-accounts/oauth/sessions/${sessionId}/connect/`, { keys })
  return response.data
}
