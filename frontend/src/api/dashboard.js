import apiClient from './client'

export async function getDashboardStats() {
  const response = await apiClient.get('/companies/dashboard-stats/')
  return response.data
}
