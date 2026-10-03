import { useCallback, useEffect, useState } from 'react'

// Quick-pick for "Min score". The backend accepts any 0-100 value; 55 is the
// cut-off the team uses for "worth a look".
export const DEFAULT_MIN_SCORE = 55

// Filter state shared by the standalone Talent Pool page and the Talent
// Pipeline tab on the job's Applicants page, so both query
// GET /api/v1/talent-pool the same way.
export function useTalentPoolFilters() {
  const [sortBy, setSortBy] = useState('score') // job view only: 'score' | 'newest'
  const [recency, setRecency] = useState('') // '' or days: '7' | '14' | '30'
  // minScoreInput is what the user types; minScore is the debounced, validated
  // value actually sent, so typing "55" doesn't fire a request for "5" first.
  const [minScoreInput, setMinScoreInput] = useState('')
  const [minScore, setMinScore] = useState('')

  useEffect(() => {
    const t = setTimeout(() => {
      const n = Number(minScoreInput)
      setMinScore(minScoreInput !== '' && Number.isInteger(n) && n >= 0 && n <= 100 ? String(n) : '')
    }, 400)
    return () => clearTimeout(t)
  }, [minScoreInput])

  // Query params for GET /api/v1/talent-pool. Scores are per job, so sort and
  // min_score are only sent when the request is scoped to a job.
  const toParams = useCallback((hasJob) => {
    const params = {}
    if (recency) params.added_within_days = recency
    if (hasJob) {
      params.sort = sortBy
      if (minScore !== '') params.min_score = minScore
    }
    return params
  }, [recency, sortBy, minScore])

  const isFiltered = (hasJob) => Boolean(recency || (hasJob && minScore !== ''))

  const clear = useCallback(() => {
    setRecency('')
    setMinScoreInput('')
    setMinScore('')
  }, [])

  return {
    sortBy, setSortBy,
    recency, setRecency,
    minScoreInput, setMinScoreInput,
    minScore,
    toParams, isFiltered, clear,
  }
}
