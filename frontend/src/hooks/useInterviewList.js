import { useCallback, useEffect, useState } from 'react'
import api from '@/lib/api'

/**
 * useInterviewList - tracks which candidates are on a specific job's
 * interview list. Job-scoped (unlike useSavedCandidates, which is global)
 *  -  the same candidate can independently be on the interview list for
 * different jobs.
 */
export function useInterviewList(jobId) {
  const [talentPoolIds, setTalentPoolIds] = useState(new Set())
  const [candidateProfileIds, setCandidateProfileIds] = useState(new Set())
  const [loading, setLoading] = useState(true)

  const refetch = useCallback(() => {
    if (!jobId) return Promise.resolve()
    return api.get('/api/v1/interview-list/ids', { params: { job_id: jobId } })
      .then(({ data }) => {
        setTalentPoolIds(new Set(data.talent_pool_profile_ids ?? []))
        setCandidateProfileIds(new Set(data.candidate_profile_ids ?? []))
      })
      .catch(() => {})
  }, [jobId])

  useEffect(() => { refetch().finally(() => setLoading(false)) }, [refetch])

  const isOnList = useCallback(({ talentPoolProfileId, candidateProfileId }) => {
    if (talentPoolProfileId && talentPoolIds.has(talentPoolProfileId)) return true
    if (candidateProfileId && candidateProfileIds.has(candidateProfileId)) return true
    return false
  }, [talentPoolIds, candidateProfileIds])

  const toggle = useCallback(async ({ talentPoolProfileId, candidateProfileId }) => {
    const onList = isOnList({ talentPoolProfileId, candidateProfileId })
    const params = {
      job_id: jobId,
      ...(talentPoolProfileId
        ? { talent_pool_profile_id: talentPoolProfileId }
        : { candidate_profile_id: candidateProfileId }),
    }

    let result
    if (onList) {
      await api.delete('/api/v1/interview-list', { params })
    } else {
      const { data } = await api.post('/api/v1/interview-list', {
        job_id: jobId,
        talent_pool_profile_id: talentPoolProfileId ?? null,
        candidate_profile_id: candidateProfileId ?? null,
      })
      result = data
    }
    await refetch()
    return result
  }, [isOnList, refetch, jobId])

  return { isOnList, toggle, loading }
}
