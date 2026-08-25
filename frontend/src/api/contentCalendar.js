import apiClient from './client'

export async function listCalendarItems(companyId, { status, platform, category, search, month } = {}) {
  const params = {}
  if (status) params.status = status
  if (platform) params.platform = platform
  if (category) params.category = category
  if (search) params.search = search
  if (month) params.month = month
  const response = await apiClient.get(`/companies/${companyId}/content-calendar/`, { params })
  return response.data
}

export async function createCalendarItem(companyId, payload) {
  const response = await apiClient.post(`/companies/${companyId}/content-calendar/`, payload)
  return response.data
}

export async function updateCalendarItem(companyId, itemId, payload) {
  const response = await apiClient.patch(`/companies/${companyId}/content-calendar/${itemId}/`, payload)
  return response.data
}

export async function deleteCalendarItem(companyId, itemId) {
  await apiClient.delete(`/companies/${companyId}/content-calendar/${itemId}/`)
}

export async function duplicateCalendarItem(companyId, itemId) {
  const response = await apiClient.post(`/companies/${companyId}/content-calendar/${itemId}/duplicate/`)
  return response.data
}

export async function approveCalendarItem(companyId, itemId) {
  const response = await apiClient.post(`/companies/${companyId}/content-calendar/${itemId}/approve/`)
  return response.data
}

export async function rejectCalendarItem(companyId, itemId, feedback) {
  const response = await apiClient.post(`/companies/${companyId}/content-calendar/${itemId}/reject/`, { feedback })
  return response.data
}

export async function downloadCalendarTemplate(companyId) {
  const response = await apiClient.get(`/companies/${companyId}/content-calendar/template/`, {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  link.download = 'content_calendar_template.xlsx'
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export async function previewCalendarImport(companyId, file) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiClient.post(`/companies/${companyId}/content-calendar/import/preview/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function commitCalendarImport(companyId, file) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiClient.post(`/companies/${companyId}/content-calendar/import/commit/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}
