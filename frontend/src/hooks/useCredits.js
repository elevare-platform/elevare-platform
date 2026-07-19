import { useState, useEffect, useCallback } from 'react'
import api from '@/lib/api'

/**
 * useCredits — fetches the authenticated employer's credit balance.
 *
 * `refetch` is exposed so callers can resync after spending/refunding a
 * credit (e.g. after a Request Introduction call succeeds or fails).
 */
export function useCredits() {
  const [balance, setBalance] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchBalance = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/api/v1/credits/balance')
      setBalance(data.balance)
    } catch {
      setBalance(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchBalance()
  }, [fetchBalance])

  return { balance, loading, refetch: fetchBalance }
}
