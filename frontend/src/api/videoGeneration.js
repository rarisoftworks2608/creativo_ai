import apiClient from './client'

export async function listVideoRequests(companyId, { status, videoType } = {}) {
  const params = {}
  if (status) params.status = status
  if (videoType) params.video_type = videoType
  const response = await apiClient.get(`/companies/${companyId}/video-generation/requests/`, { params })
  return response.data
}

export async function createVideoRequest(companyId, payload) {
  const response = await apiClient.post(`/companies/${companyId}/video-generation/requests/`, payload)
  return response.data
}

export async function getVideoRequest(companyId, requestId) {
  const response = await apiClient.get(`/companies/${companyId}/video-generation/requests/${requestId}/`)
  return response.data
}

export async function retryVideoRequest(companyId, requestId) {
  const response = await apiClient.post(`/companies/${companyId}/video-generation/requests/${requestId}/retry/`)
  return response.data
}

export async function rerenderVideo(companyId, requestId, options = {}) {
  const response = await apiClient.post(`/companies/${companyId}/video-generation/requests/${requestId}/rerender/`, options)
  return response.data
}

export async function updateVideoScene(companyId, requestId, sceneId, payload) {
  const response = await apiClient.patch(`/companies/${companyId}/video-generation/requests/${requestId}/scenes/${sceneId}/`, payload)
  return response.data
}

export async function regenerateSceneImage(companyId, requestId, sceneId) {
  const response = await apiClient.post(
    `/companies/${companyId}/video-generation/requests/${requestId}/scenes/${sceneId}/regenerate-image/`,
  )
  return response.data
}
