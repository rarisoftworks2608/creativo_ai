import apiClient from './client'

export async function getAnalyticsSummary(companyId, { start, end, platform } = {}) {
  const params = {}
  if (start) params.start = start
  if (end) params.end = end
  if (platform) params.platform = platform
  const response = await apiClient.get(`/companies/${companyId}/analytics/summary/`, { params })
  return response.data
}

export async function listPostMetrics(companyId, params = {}) {
  const response = await apiClient.get(`/companies/${companyId}/analytics/posts/`, { params })
  return response.data
}

export async function syncAnalytics(companyId) {
  const response = await apiClient.post(`/companies/${companyId}/analytics/sync/`)
  return response.data
}

export async function listAnalyticsSyncLogs(companyId) {
  const response = await apiClient.get(`/companies/${companyId}/analytics/sync-logs/`)
  return response.data
}

export async function getAnalyticsOverview(days = 30) {
  const response = await apiClient.get('/analytics/overview/', { params: { days } })
  return response.data
}
