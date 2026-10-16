import { useState, useEffect } from 'react'
import api from '@/lib/api'

/**
 * useInterviewPricing - what an AI interview costs the signed-in employer's
 * organization, from GET /api/v1/interviews/pricing:
 * { credits_per_interview, balance, charged }. Null until loaded, or if the
 * request fails (the screens then simply show no interview cost).
 */
export function useInterviewPricing() {
  const [pricing, setPricing] = useState(null)

  useEffect(() => {
    let cancelled = false
    api.get('/api/v1/interviews/pricing')
      .then(({ data }) => { if (!cancelled) setPricing(data) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  return pricing
}
