import apiClient from './client'

export async function listNotifications({ isRead } = {}) {
  const params = {}
  if (isRead !== undefined) params.is_read = isRead
  const response = await apiClient.get('/notifications/', { params })
  return response.data
}

export async function getUnreadCount() {
  const response = await apiClient.get('/notifications/unread-count/')
  return response.data.count
}

export async function markNotificationRead(notificationId) {
  const response = await apiClient.post(`/notifications/${notificationId}/read/`)
  return response.data
}

export async function markAllNotificationsRead() {
  const response = await apiClient.post('/notifications/mark-all-read/')
  return response.data
}
