import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

const TOKEN_KEY = 'ams_tokens'

export function getTokens() {
  const raw = localStorage.getItem(TOKEN_KEY)
  return raw ? JSON.parse(raw) : null
}

export function setTokens(tokens) {
  if (tokens) {
    localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens))
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

const apiClient = axios.create({ baseURL: BASE_URL })

apiClient.interceptors.request.use((config) => {
  const tokens = getTokens()
  if (tokens?.access) {
    config.headers.Authorization = `Bearer ${tokens.access}`
  }
  return config
})

let refreshPromise = null

async function refreshAccessToken() {
  const tokens = getTokens()
  if (!tokens?.refresh) throw new Error('No refresh token available.')

  const response = await axios.post(`${BASE_URL}/auth/refresh/`, { refresh: tokens.refresh })
  const nextTokens = { access: response.data.access, refresh: response.data.refresh ?? tokens.refresh }
  setTokens(nextTokens)
  return nextTokens
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error
    const isAuthEndpoint = config?.url?.includes('/auth/login/') || config?.url?.includes('/auth/refresh/')

    if (response?.status === 401 && !config._retried && !isAuthEndpoint) {
      config._retried = true
      try {
        refreshPromise = refreshPromise || refreshAccessToken()
        const tokens = await refreshPromise
        refreshPromise = null
        config.headers.Authorization = `Bearer ${tokens.access}`
        return apiClient(config)
      } catch (refreshError) {
        refreshPromise = null
        setTokens(null)
        window.location.assign('/login')
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  },
)

export function extractErrorMessage(error, fallback = 'Something went wrong.') {
  const data = error?.response?.data
  if (!data) return error?.message || fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  const firstKey = Object.keys(data)[0]
  if (firstKey) {
    const value = data[firstKey]
    const message = Array.isArray(value) ? value[0] : value
    return firstKey === 'non_field_errors' ? message : `${firstKey}: ${message}`
  }
  return fallback
}

export default apiClient
