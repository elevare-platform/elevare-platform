import { useCallback, useEffect, useState } from 'react'
import api from '@/lib/api'

/**
 * useRescore - the candidates on one job who have no usable score (their CV could not
 * be read, or scoring failed) and a way to rescore them.
 *
 * `status` is { applications, pipeline, total }, null until loaded (or if it cannot be
 * loaded: the screens then show nothing). `rescore(body)` rescores everyone who needs it
 * (a batch at a time) or, with { application_id } / { talent_pool_profile_id }, one
 * candidate. It resolves to { ok: true, data } or { ok: false, message }; the message is
 * the server's own wording, so a plan limit reads as one.
 */
export function useRescore(jobId) {
  const [status, setStatus] = useState(null)
  const [working, setWorking] = useState(false)
  const [result, setResult] = useState(null)

  const refresh = useCallback(
    () => api.get(`/api/v1/rescore/jobs/${jobId}`)
      .then(({ data }) => setStatus(data))
      .catch(() => {}),
    [jobId],
  )

  useEffect(() => { refresh() }, [refresh])

  const rescore = useCallback(async (body = {}) => {
    setWorking(true)
    try {
      const { data } = await api.post(`/api/v1/rescore/jobs/${jobId}`, body)
      // The bar above the list reports "Rescore all"; one candidate's answer is shown
      // by the caller next to that candidate.
      const oneCandidate = Boolean(body.application_id || body.talent_pool_profile_id)
      if (!oneCandidate) setResult(data)
      await refresh()
      return { ok: true, data }
    } catch (err) {
      return {
        ok: false,
        message: err?.response?.data?.message ?? 'Could not start the rescore. Please try again.',
      }
    } finally {
      setWorking(false)
    }
  }, [jobId, refresh])

  const dismissResult = useCallback(() => setResult(null), [])

  return { status, working, result, rescore, dismissResult, refresh }
}
