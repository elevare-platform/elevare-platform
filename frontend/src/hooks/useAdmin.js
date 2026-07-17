import { useState, useCallback } from 'react'
import api from '@/lib/api'

export function useAdmin() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const request = useCallback(async (fn) => {
    setLoading(true)
    setError(null)
    try {
      return await fn()
    } catch (err) {
      const msg = err.response?.data?.message ?? 'Something went wrong'
      setError(msg)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  // Users
  const listUsers = (params) =>
    request(() => api.get('/api/v1/admin/users', { params }).then((r) => r.data))

  const updateUserStatus = (id, status) =>
    request(() => api.patch(`/api/v1/admin/users/${id}`, { status }).then((r) => r.data))

  const bulkUpdateUsers = (user_ids, action) =>
    request(() => api.patch('/api/v1/admin/users/bulk', { user_ids, action }).then((r) => r.data))

  // Jobs
  const listJobs = (params) =>
    request(() => api.get('/api/v1/admin/jobs', { params }).then((r) => r.data))

  const moderateJob = (id, action, reason = null) =>
    request(() => api.patch(`/api/v1/admin/jobs/${id}/moderate`, { action, reason }).then((r) => r.data))

  const bulkUpdateJobs = (job_ids, action) =>
    request(() => api.patch('/api/v1/admin/jobs/bulk', { job_ids, action }).then((r) => r.data))

  // Applications
  const listApplications = (params) =>
    request(() => api.get('/api/v1/admin/applications', { params }).then((r) => r.data))

  // Stats
  const getStats = () =>
    request(() => api.get('/api/v1/admin/stats').then((r) => r.data))

  // Audit log
  const listAuditLog = (params) =>
    request(() => api.get('/api/v1/admin/audit-log', { params }).then((r) => r.data))

  // CV presigned URL
  const getCvUrl = (cvId) =>
    request(() => api.get(`/api/v1/candidates/cv/${cvId}/download`).then((r) => r.data))

  // Testimonials
  const listTestimonials = (params) =>
    request(() => api.get('/api/v1/admin/testimonials', { params }).then((r) => r.data))

  const moderateTestimonial = (id, status) =>
    request(() => api.patch(`/api/v1/admin/testimonials/${id}`, { status }).then((r) => r.data))

  // Credits
  const grantEmployerCredits = (employerId, amount, reason) =>
    request(() =>
      api.patch(`/api/v1/admin/employers/${employerId}/credits`, { amount, reason })
        .then((r) => r.data)
    )

  return {
    loading,
    error,
    listUsers,
    updateUserStatus,
    bulkUpdateUsers,
    listJobs,
    moderateJob,
    bulkUpdateJobs,
    listApplications,
    getStats,
    listAuditLog,
    getCvUrl,
    listTestimonials,
    moderateTestimonial,
    grantEmployerCredits,
  }
}
