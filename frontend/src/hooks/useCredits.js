import { useState, useEffect, useCallback } from 'react'
import api from '@/lib/api'

/**
 * useCredits - fetches the authenticated employer's credit balance.
 *
 * `balance` is everything the organization can spend. It is made up of
 * `planCredits` (included in its plan, spent first, replaced at each renewal at
 * `planCreditsResetAt`) and `purchasedCredits` (bought or granted, never expire).
 *
 * `refetch` is exposed so callers can resync after spending/refunding a
 * credit (e.g. after a Request Introduction call succeeds or fails).
 */
export function useCredits() {
  const [balance, setBalance] = useState(null)
  const [planCredits, setPlanCredits] = useState(0)
  const [purchasedCredits, setPurchasedCredits] = useState(0)
  const [planCreditsResetAt, setPlanCreditsResetAt] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchBalance = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/api/v1/credits/balance')
      setBalance(data.balance)
      setPlanCredits(data.plan_credits ?? 0)
      setPurchasedCredits(data.purchased_credits ?? data.balance)
      setPlanCreditsResetAt(data.plan_credits_reset_at ?? null)
    } catch {
      setBalance(null)
      setPlanCredits(0)
      setPurchasedCredits(0)
      setPlanCreditsResetAt(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchBalance()
  }, [fetchBalance])

  return {
    balance,
    planCredits,
    purchasedCredits,
    planCreditsResetAt,
    loading,
    refetch: fetchBalance,
  }
}
