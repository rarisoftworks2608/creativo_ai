import apiClient from './client'

export async function fetchPlatformSettings() {
  const response = await apiClient.get('/platform-settings/')
  return response.data
}

export async function updatePlatformSettings(data) {
  const response = await apiClient.patch('/platform-settings/', data)
  return response.data
}
