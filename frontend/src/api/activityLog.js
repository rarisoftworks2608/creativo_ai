import apiClient from './client'

export async function listActivityLog(params = {}) {
  const response = await apiClient.get('/activity-log/', { params })
  return response.data
}
