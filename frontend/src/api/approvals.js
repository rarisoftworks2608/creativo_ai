import apiClient from './client'

export async function listApprovalQueue({ status, company, platform, search, page } = {}) {
  const params = {}
  if (status) params.status = status
  if (company) params.company = company
  if (platform) params.platform = platform
  if (search) params.search = search
  if (page) params.page = page
  const response = await apiClient.get('/approvals/', { params })
  return response.data
}

export async function getApprovalStats() {
  const response = await apiClient.get('/approvals/stats/')
  return response.data
}

export async function getItemHistory(companyId, itemId) {
  const response = await apiClient.get(`/companies/${companyId}/content-calendar/${itemId}/history/`)
  return response.data
}
