import { useState, useCallback } from 'react'
import api from '@/lib/api'

export function useCVParser() {
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

  const submitCV = (file) => {
    const form = new FormData()
    form.append('file', file)
    return request(() =>
      api.post('/api/v1/cv-parsing/submit', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }).then((r) => r.data)
    )
  }

  const submitBatch = (files) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return request(() =>
      api.post('/api/v1/cv-parsing/submit/batch', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }).then((r) => r.data)
    )
  }

  const listSubmissions = (params) =>
    request(() => api.get('/api/v1/cv-parsing/submissions', { params }).then((r) => r.data))

  const getSubmission = (id) =>
    request(() => api.get(`/api/v1/cv-parsing/submissions/${id}`).then((r) => r.data))

  const pollSubmission = (id) =>
    api.get(`/api/v1/cv-parsing/submissions/${id}`).then((r) => r.data)

  const downloadCV = (id) =>
    request(() => api.get(`/api/v1/cv-parsing/submissions/${id}/download`).then((r) => r.data))

  const createCandidate = (id) =>
    request(() => api.post(`/api/v1/cv-parsing/submissions/${id}/create-candidate`).then((r) => r.data))

  const getMonthlyCosts = () =>
    request(() => api.get('/api/v1/cv-parsing/costs').then((r) => r.data))

  return {
    loading,
    error,
    submitCV,
    submitBatch,
    listSubmissions,
    getSubmission,
    pollSubmission,
    downloadCV,
    createCandidate,
    getMonthlyCosts,
  }
}
