import apiClient from './client'
import { downloadFile } from '../utils/download'

const companyBase = (companyId) => `/companies/${companyId}/reports`

export async function listCompanyReports(companyId, params = {}) {
  const response = await apiClient.get(`${companyBase(companyId)}/`, { params })
  return response.data
}

export async function createCompanyReport(companyId, payload) {
  const response = await apiClient.post(`${companyBase(companyId)}/`, payload)
  return response.data
}

export async function getCompanyReport(companyId, reportId) {
  const response = await apiClient.get(`${companyBase(companyId)}/${reportId}/`)
  return response.data
}

export async function deleteCompanyReport(companyId, reportId) {
  await apiClient.delete(`${companyBase(companyId)}/${reportId}/`)
}

export async function regenerateCompanyReport(companyId, reportId) {
  const response = await apiClient.post(`${companyBase(companyId)}/${reportId}/regenerate/`)
  return response.data
}

export async function sendCompanyReport(companyId, reportId, { email = true, whatsapp = true } = {}) {
  const response = await apiClient.post(`${companyBase(companyId)}/${reportId}/send/`, { email, whatsapp })
  return response.data
}

export function downloadCompanyReport(companyId, reportId, fileFormat = 'pdf') {
  return downloadFile(`${companyBase(companyId)}/${reportId}/download/`, `report.${fileFormat}`, { file_format: fileFormat })
}

export async function listAdminReports(params = {}) {
  const response = await apiClient.get('/reports/', { params })
  return response.data
}

export async function createAdminReport(payload) {
  const response = await apiClient.post('/reports/', payload)
  return response.data
}

export async function getAdminReport(reportId) {
  const response = await apiClient.get(`/reports/${reportId}/`)
  return response.data
}

export async function deleteAdminReport(reportId) {
  await apiClient.delete(`/reports/${reportId}/`)
}

export async function regenerateAdminReport(reportId) {
  const response = await apiClient.post(`/reports/${reportId}/regenerate/`)
  return response.data
}

export function downloadAdminReport(reportId, fileFormat = 'pdf') {
  return downloadFile(`/reports/${reportId}/download/`, `report.${fileFormat}`, { file_format: fileFormat })
}
