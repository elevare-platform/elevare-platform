import { useState, useCallback } from 'react'
import api from '@/lib/api'

/**
 * useTalentMatches — fetches AI-ranked talent pool profiles for a job.
 *
 * `notReady` distinguishes "job embedding not generated yet" (backend
 * raises a VALIDATION_FAILED error) from a genuine fetch failure, so the
 * UI can show a soft "check back shortly" message instead of an error.
 */
export function useTalentMatches(jobId) {
  const [matches, setMatches] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [notReady, setNotReady] = useState(false)

  const fetchTalentMatches = useCallback(async (limit = 20) => {
    setLoading(true)
    setError(null)
    setNotReady(false)
    try {
      const { data } = await api.get(`/api/v1/jobs/${jobId}/talent-matches`, {
        params: { limit },
      })
      setMatches(data.items ?? [])
    } catch (err) {
      if (err?.response?.data?.code === 'VALIDATION_FAILED') {
        setNotReady(true)
      } else {
        setError(err?.response?.data?.message ?? err.message ?? 'Failed to load AI matches')
      }
    } finally {
      setLoading(false)
    }
  }, [jobId])

  return { matches, loading, error, notReady, fetchTalentMatches }
}
