import apiClient from '../api/client'

// Downloads an authenticated file endpoint (JWT header required, so a plain <a href> won't do).
export async function downloadFile(url, filename, params = {}) {
  const response = await apiClient.get(url, { params, responseType: 'blob' })
  const disposition = response.headers?.['content-disposition'] || ''
  const match = disposition.match(/filename="?([^";]+)"?/i)
  const objectUrl = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = match ? match[1] : filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(objectUrl)
}
