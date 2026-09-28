import apiClient, { setTokens } from './client'

export async function login(email, password) {
  const response = await apiClient.post('/auth/login/', { email, password })
  setTokens({ access: response.data.access, refresh: response.data.refresh })
  return response.data.user
}

export async function logout() {
  const raw = localStorage.getItem('ams_tokens')
  const tokens = raw ? JSON.parse(raw) : null
  try {
    if (tokens?.refresh) {
      await apiClient.post('/auth/logout/', { refresh: tokens.refresh })
    }
  } finally {
    setTokens(null)
  }
}

export async function fetchProfile() {
  const response = await apiClient.get('/auth/profile/')
  return response.data
}

export async function updateProfile(data) {
  const hasFile = data.avatar instanceof File
  let payload = data
  let headers

  if (hasFile) {
    payload = new FormData()
    Object.entries(data).forEach(([key, value]) => {
      if (value !== undefined && value !== null) payload.append(key, value)
    })
    headers = { 'Content-Type': 'multipart/form-data' }
  }

  const response = await apiClient.patch('/auth/profile/', payload, headers ? { headers } : undefined)
  return response.data
}

export async function fetchLoginHistory() {
  const response = await apiClient.get('/auth/login-history/')
  return response.data
}

export async function requestPasswordReset(email) {
  const response = await apiClient.post('/auth/forgot-password/', { email })
  return response.data
}

export async function resetPassword({ uid, token, newPassword }) {
  const response = await apiClient.post('/auth/reset-password/', { uid, token, new_password: newPassword })
  return response.data
}

export async function changePassword({ oldPassword, newPassword }) {
  const response = await apiClient.post('/auth/change-password/', {
    old_password: oldPassword, new_password: newPassword,
  })
  return response.data
}
