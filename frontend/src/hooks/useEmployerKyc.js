import { useState, useCallback } from 'react'
import api from '@/lib/api'

export const KYC_DOCUMENT_TYPES = ['Business Registration', 'Tax ID', 'Proof of Address']

export function useEmployerKyc() {
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

  const getKycStatus = () =>
    request(() => api.get('/api/v1/employer/kyc').then((r) => r.data))

  const uploadKycDocument = (file, documentType) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('document_type', documentType)
    return request(() =>
      api
        .post('/api/v1/employer/kyc/documents', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        .then((r) => r.data)
    )
  }

  const deleteKycDocument = (documentId) =>
    request(() => api.delete(`/api/v1/employer/kyc/documents/${documentId}`).then((r) => r.data))

  const getKycDocumentUrl = (documentId) =>
    request(() =>
      api.get(`/api/v1/employer/kyc/documents/${documentId}/url`).then((r) => r.data.data.url)
    )

  const submitKyc = () =>
    request(() => api.post('/api/v1/employer/kyc/submit').then((r) => r.data))

  return {
    loading,
    error,
    getKycStatus,
    uploadKycDocument,
    deleteKycDocument,
    getKycDocumentUrl,
    submitKyc,
  }
}
