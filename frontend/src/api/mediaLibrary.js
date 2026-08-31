import apiClient from './client'

export async function listMediaLibrary(companyId, { type, search } = {}) {
  const params = {}
  if (type) params.type = type
  if (search) params.search = search
  const response = await apiClient.get(`/companies/${companyId}/media-library/`, { params })
  return response.data
}
