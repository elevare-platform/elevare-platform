import { useState, useEffect, useCallback } from 'react'
import api from '@/lib/api'

/**
 * useCandidateIntroductions — introduction requests made about the
 * authenticated (self-registered) candidate. GET /api/v1/candidates/me/introductions
 */
export function useCandidateIntroductions() {
  const [introductions, setIntroductions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchIntroductions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await api.get('/api/v1/candidates/me/introductions')
      setIntroductions(data ?? [])
    } catch (err) {
      setError(err?.response?.data?.message ?? 'Failed to load introduction requests')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchIntroductions()
  }, [fetchIntroductions])

  return { introductions, loading, error, refetch: fetchIntroductions }
}
