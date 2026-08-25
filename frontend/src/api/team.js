import apiClient from './client'

export async function listTeam() {
  const response = await apiClient.get('/auth/users/', { params: { role: 'admin' } })
  return response.data
}

export async function createAdmin(payload) {
  const response = await apiClient.post('/auth/users/', { ...payload, role: 'admin' })
  return response.data
}

export async function setAdminActive(userId, isActive) {
  return setUserActive(userId, isActive)
}

// Generic - PATCH /auth/users/<id>/ works for any role (admin or client), so this is
// reused by the Access Control page for toggling a client login too.
export async function setUserActive(userId, isActive) {
  const response = await apiClient.patch(`/auth/users/${userId}/`, { is_active: isActive })
  return response.data
}
