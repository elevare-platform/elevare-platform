import { useState, useEffect, useCallback } from 'react'
import api from '@/lib/api'

/**
 * useCandidateProfile — fetches and manages the candidate's ProfileResponse.
 *
 * Fetches GET /api/v1/candidates/me once on mount. Exposes optimistic
 * mutation helpers for CVs and documents so callers can update local state
 * after write operations without refetching the full profile.
 *
 * @returns {{
 *   profile: Object|null,
 *   loading: boolean,
 *   error: string|null,
 *   refetch: () => void,
 *   setCvs: (updater: CandidateCvsResponse[]|Function) => void,
 *   setDocuments: (updater: CandidateDocumentsResponse[]|Function) => void,
 * }}
 */
export function useCandidateProfile() {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // Increment to trigger a re-fetch (Requirement 2.5 — only re-fetches on explicit refresh)
  const [fetchTick, setFetchTick] = useState(0)

  useEffect(() => {
    let cancelled = false

    const fetchProfile = async () => {
      setLoading(true)
      setError(null)

      try {
        const { data } = await api.get('/api/v1/candidates/me')
        if (!cancelled) setProfile(data)
      } catch (err) {
        if (!cancelled) {
          setError(err?.response?.data?.detail ?? err.message ?? 'Failed to load profile')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchProfile()
    return () => { cancelled = true }
  }, [fetchTick])

  // Explicit refresh — increments tick to re-run the effect (Requirement 2.4)
  const refetch = useCallback(() => {
    setFetchTick((t) => t + 1)
  }, [])

  // Optimistic CV list updater — accepts a new array or an updater function
  const setCvs = useCallback((updater) => {
    setProfile((prev) => {
      if (!prev) return prev
      const nextCvs = typeof updater === 'function' ? updater(prev.cvs ?? []) : updater
      return { ...prev, cvs: nextCvs }
    })
  }, [])

  // Optimistic documents list updater — accepts a new array or an updater function
  const setDocuments = useCallback((updater) => {
    setProfile((prev) => {
      if (!prev) return prev
      const nextDocs = typeof updater === 'function' ? updater(prev.documents ?? []) : updater
      return { ...prev, documents: nextDocs }
    })
  }, [])

  return { profile, loading, error, refetch, setCvs, setDocuments }
}
