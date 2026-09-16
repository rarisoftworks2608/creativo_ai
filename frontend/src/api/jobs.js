import apiClient from './client'

export async function listJobs(params = {}) {
  const response = await apiClient.get('/companies/jobs/', { params })
  return response.data
}

export async function cancelJob(jobType, jobId) {
  const response = await apiClient.post(`/companies/jobs/${jobType}/${jobId}/cancel/`)
  return response.data
}
