import { useState, useCallback } from 'react'
import api from '@/lib/api'

export function useTeam() {
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

  const listMembers = () =>
    request(() => api.get('/api/v1/employer/team').then((r) => r.data))

  const inviteMember = (email) =>
    request(() => api.post('/api/v1/employer/team/invite', { email }).then((r) => r.data))

  const removeMember = (userId) =>
    request(() => api.delete(`/api/v1/employer/team/${userId}`).then((r) => r.data))

  return {
    loading,
    error,
    listMembers,
    inviteMember,
    removeMember,
  }
}
