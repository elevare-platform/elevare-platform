import { useState, useCallback } from 'react'
import api from '@/lib/api'

export function useBilling() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const request = useCallback(async (fn) => {
    setLoading(true)
    setError(null)
    try {
      return await fn()
    } catch (err) {
      const msg = err.response?.data?.message ?? 'Something went wrong'
      setError(msg)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  const getCurrentSubscription = () =>
    request(() => api.get('/api/v1/billing/subscription').then((r) => r.data))

  const listPlans = () =>
    request(() => api.get('/api/v1/billing/plans').then((r) => r.data))

  const listCreditPackages = () =>
    request(() => api.get('/api/v1/billing/credit-packages').then((r) => r.data))

  const listPayments = () =>
    request(() => api.get('/api/v1/billing/payments').then((r) => r.data))

  const startSubscriptionCheckout = (planCode) =>
    request(() =>
      api.post('/api/v1/billing/subscription/checkout', { plan_code: planCode }).then((r) => r.data)
    )

  const startCreditCheckout = (creditPackageCode) =>
    request(() =>
      api.post('/api/v1/billing/credits/checkout', { credit_package_code: creditPackageCode }).then((r) => r.data)
    )

  const verifyCheckout = (reference) =>
    request(() => api.get(`/api/v1/billing/checkout/${reference}/verify`).then((r) => r.data))

  const cancelSubscription = () =>
    request(() => api.post('/api/v1/billing/subscription/cancel').then((r) => r.data))

  return {
    loading,
    error,
    getCurrentSubscription,
    listPlans,
    listCreditPackages,
    listPayments,
    startSubscriptionCheckout,
    startCreditCheckout,
    verifyCheckout,
    cancelSubscription,
  }
}
