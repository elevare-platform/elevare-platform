import { useCallback, useEffect, useState } from 'react'
import api from '@/lib/api'

/**
 * useSavedCandidates - tracks which candidates the employer has saved
 * (the global "heart" bookmark, distinct from job-scoped Shortlist status
 * and the per-job Interview List).
 *
 * Two id sets because callers address a candidate differently depending on
 * where they're rendered: search/AI-match results carry
 * talent_pool_profile_id directly, while the applicants list only has
 * candidate_profile_id on hand.
 */
export function useSavedCandidates() {
  const [talentPoolIds, setTalentPoolIds] = useState(new Set())
  const [candidateProfileIds, setCandidateProfileIds] = useState(new Set())
  const [loading, setLoading] = useState(true)

  const refetch = useCallback(() => {
    return api.get('/api/v1/saved-candidates/ids')
      .then(({ data }) => {
        setTalentPoolIds(new Set(data.talent_pool_profile_ids ?? []))
        setCandidateProfileIds(new Set(data.candidate_profile_ids ?? []))
      })
      .catch(() => {})
  }, [])

  useEffect(() => { refetch().finally(() => setLoading(false)) }, [refetch])

  const isSaved = useCallback(({ talentPoolProfileId, candidateProfileId }) => {
    if (talentPoolProfileId && talentPoolIds.has(talentPoolProfileId)) return true
    if (candidateProfileId && candidateProfileIds.has(candidateProfileId)) return true
    return false
  }, [talentPoolIds, candidateProfileIds])

  const toggle = useCallback(async ({ talentPoolProfileId, candidateProfileId }) => {
    const saved = isSaved({ talentPoolProfileId, candidateProfileId })
    const params = talentPoolProfileId
      ? { talent_pool_profile_id: talentPoolProfileId }
      : { candidate_profile_id: candidateProfileId }

    if (saved) {
      await api.delete('/api/v1/saved-candidates', { params })
    } else {
      await api.post('/api/v1/saved-candidates', {
        talent_pool_profile_id: talentPoolProfileId ?? null,
        candidate_profile_id: candidateProfileId ?? null,
      })
    }
    await refetch()
  }, [isSaved, refetch])

  return { isSaved, toggle, loading }
}
