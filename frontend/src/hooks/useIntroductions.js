import { useState, useEffect, useCallback } from 'react'
import api from '@/lib/api'

/**
 * useIntroductions — fetches every introduction request the authenticated
 * employer has made, across all jobs (GET /api/v1/introductions/mine).
 */
export function useIntroductions() {
  const [introductions, setIntroductions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchIntroductions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await api.get('/api/v1/introductions/mine')
      setIntroductions(data ?? [])
    } catch (err) {
      setError(err?.response?.data?.message ?? 'Failed to load introductions')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchIntroductions()
  }, [fetchIntroductions])

  return { introductions, loading, error, refetch: fetchIntroductions }
}
