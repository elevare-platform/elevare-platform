import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { CreditCard, Coins, Receipt, Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/context/AuthContext'
import { useBilling } from '@/hooks/useBilling'
import { useCredits } from '@/hooks/useCredits'
import { cn } from '@/lib/utils'

function formatPrice(priceKobo, currency = 'NGN') {
  if (priceKobo === 0) return 'Free'
  const symbol = currency === 'NGN' ? '₦' : currency
  return `${symbol}${(priceKobo / 100).toLocaleString()}`
}

function formatDate(isoString) {
  if (!isoString) return null
  return new Date(isoString).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

const PAYMENT_STATUS = {
  SUCCEEDED: { icon: CheckCircle2, label: 'Succeeded', className: 'bg-green-50 text-green-700 border-green-200' },
  PENDING: { icon: Clock, label: 'Pending', className: 'bg-amber-50 text-amber-700 border-amber-200' },
  FAILED: { icon: XCircle, label: 'Failed', className: 'bg-red-50 text-red-700 border-red-200' },
}

function PaymentStatusBadge({ status }) {
  const cfg = PAYMENT_STATUS[status] ?? PAYMENT_STATUS.PENDING
  const Icon = cfg.icon
  return (
    <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border', cfg.className)}>
      <Icon size={12} /> {cfg.label}
    </span>
  )
}

// Not yet subscribed / not yet configured on the backend — surfaced as a
// plain message rather than a generic error, since it's an expected state
// (Paystack business verification pending), not a bug.
function PaymentsNotAvailableNotice() {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
      Payments aren't set up yet on our end.{' '}
      <a href="/contact" className="underline font-medium">Contact us</a> and we'll get you set up directly.
    </div>
  )
}

export default function BillingPage() {
  const { user } = useAuth()
  const canManage = user?.organization_role === 'OWNER' || user?.organization_role === 'ADMIN'
  const {
    getCurrentSubscription, listPlans, listCreditPackages, listPayments, startSubscriptionCheckout, startCreditCheckout,
    cancelSubscription,
  } = useBilling()
  const { balance, loading: balanceLoading } = useCredits()

  const [subscription, setSubscription] = useState(null)
  const [plans, setPlans] = useState([])
  const [packages, setPackages] = useState([])
  const [payments, setPayments] = useState([])
  const [loading, setLoading] = useState(true)
  const [actionError, setActionError] = useState(null)
  const [actingOn, setActingOn] = useState(null) // credit package code currently checking out

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [sub, planList, pkgs, pays] = await Promise.all([
        getCurrentSubscription(),
        listPlans(),
        listCreditPackages(),
        listPayments(),
      ])
      setSubscription(sub)
      setPlans(planList)
      setPackages(pkgs)
      setPayments(pays)
    } catch {
      // handled via hook's error state per-call; page still renders with what it has
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => { load() }, [load])

  const handleBuyCredits = async (packageCode) => {
    setActionError(null)
    setActingOn(packageCode)
    try {
      const { checkout_url } = await startCreditCheckout(packageCode)
      if (checkout_url) window.open(checkout_url, '_blank', 'noopener,noreferrer')
    } catch (err) {
      if (err.response?.data?.code === 'PAYMENTS_NOT_CONFIGURED') {
        setActionError('PAYMENTS_NOT_CONFIGURED')
      } else {
        setActionError(err.response?.data?.message ?? 'Could not start checkout.')
      }
    } finally {
      setActingOn(null)
    }
  }

  const handleUpgrade = async () => {
    const targetPlan = plans.find((p) => p.code === 'professional')
    const priceLabel = targetPlan
      ? `${formatPrice(targetPlan.price_kobo, targetPlan.currency)}/${targetPlan.interval.toLowerCase()}`
      : 'the plan price'
    if (!window.confirm(
      `You'll be charged ${priceLabel} automatically, starting today, until you cancel. ` +
      'You can cancel anytime from this page. Continue to payment?'
    )) {
      return
    }
    setActionError(null)
    setActingOn('upgrade')
    try {
      const { checkout_url, activated } = await startSubscriptionCheckout('professional')
      if (checkout_url) {
        window.open(checkout_url, '_blank', 'noopener,noreferrer')
      } else if (activated) {
        await load()
      }
    } catch (err) {
      if (err.response?.data?.code === 'PAYMENTS_NOT_CONFIGURED') {
        setActionError('PAYMENTS_NOT_CONFIGURED')
      } else {
        setActionError(err.response?.data?.message ?? 'Could not start checkout.')
      }
    } finally {
      setActingOn(null)
    }
  }

  const handleCancel = async () => {
    if (!window.confirm(
      `This will stop renewal. You'll keep ${plan?.name} until ${formatDate(subscription?.current_period_end)}, then move to Starter. Continue?`
    )) {
      return
    }
    setActionError(null)
    setActingOn('cancel')
    try {
      const sub = await cancelSubscription()
      setSubscription(sub)
    } catch (err) {
      setActionError(err.response?.data?.message ?? 'Could not cancel subscription.')
    } finally {
      setActingOn(null)
    }
  }

  const plan = subscription?.plan
  const isStarter = plan?.code === 'starter'
  const isCanceling = subscription?.cancel_at_period_end === true

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-12 space-y-8">
          <div>
            <h1 className="text-2xl font-bold text-text">Billing</h1>
            <p className="text-sm text-text-muted mt-1">
              Your plan, credits, and payment history.
            </p>
          </div>

          {loading ? (
            <div className="flex justify-center py-16">
              <Loader2 size={24} className="animate-spin text-brand-blue" />
            </div>
          ) : (
            <>
              {actionError === 'PAYMENTS_NOT_CONFIGURED' && <PaymentsNotAvailableNotice />}
              {actionError && actionError !== 'PAYMENTS_NOT_CONFIGURED' && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {actionError}
                </div>
              )}

              {/* Current plan */}
              <section className="bg-white rounded-xl border border-border p-6">
                <div className="flex items-center gap-2 mb-4">
                  <CreditCard size={16} className="text-brand-blue" />
                  <h2 className="font-semibold text-text text-sm">Current plan</h2>
                </div>
                <div className="flex items-center justify-between flex-wrap gap-4">
                  <div>
                    <p className="text-xl font-bold text-text">{plan?.name}</p>
                    <p className="text-sm text-text-muted mt-0.5">
                      {formatPrice(plan?.price_kobo, plan?.currency)}
                      {plan?.price_kobo > 0 && ` / ${plan.interval.toLowerCase()}`}
                    </p>
                    {subscription?.current_period_end && (
                      <p className={cn('text-xs mt-1', isCanceling ? 'text-amber-700 font-medium' : 'text-text-muted')}>
                        {isCanceling ? 'Ends' : 'Renews'} {formatDate(subscription.current_period_end)}
                        {isCanceling && ' (moves to Starter after this date)'}
                      </p>
                    )}
                  </div>
                  {isStarter && canManage && (
                    <div className="text-right">
                      <Button onClick={handleUpgrade} disabled={actingOn === 'upgrade'}>
                        {actingOn === 'upgrade' ? <Loader2 size={16} className="animate-spin mr-1.5" /> : null}
                        Upgrade to Professional
                      </Button>
                      <p className="text-xs text-text-muted mt-1.5">
                        Billed automatically until you cancel.
                      </p>
                    </div>
                  )}
                  {isStarter && !canManage && (
                    <p className="text-xs text-text-muted">Ask an owner or admin to upgrade.</p>
                  )}
                  {!isStarter && canManage && !isCanceling && (
                    <Button variant="outline" onClick={handleCancel} disabled={actingOn === 'cancel'}>
                      {actingOn === 'cancel' ? <Loader2 size={16} className="animate-spin mr-1.5" /> : null}
                      Cancel subscription
                    </Button>
                  )}
                  {!isStarter && !canManage && !isCanceling && (
                    <p className="text-xs text-text-muted">Ask an owner or admin to cancel.</p>
                  )}
                </div>
                <p className="text-xs text-text-muted mt-4">
                  See the full <Link to="/pricing" className="text-brand-blue hover:underline">plan comparison</Link>.
                </p>
              </section>

              {/* Credits */}
              <section className="bg-white rounded-xl border border-border p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Coins size={16} className="text-brand-blue" />
                  <h2 className="font-semibold text-text text-sm">Credits</h2>
                </div>
                <p className="text-sm text-text-muted mb-4">
                  Balance: <span className="font-semibold text-text">{balanceLoading ? '…' : balance ?? 0}</span> credits. Used when requesting candidate introductions.
                </p>

                {canManage ? (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {packages.map((pkg) => (
                      <div key={pkg.code} className="rounded-lg border border-border p-4 text-center">
                        <p className="font-semibold text-text text-sm">{pkg.name}</p>
                        <p className="text-xs text-text-muted mt-0.5">{pkg.credits} credits</p>
                        <p className="text-lg font-bold text-text mt-2">{formatPrice(pkg.price_kobo, pkg.currency)}</p>
                        <Button
                          size="sm"
                          variant="outline"
                          className="w-full mt-3"
                          onClick={() => handleBuyCredits(pkg.code)}
                          disabled={actingOn === pkg.code}
                        >
                          {actingOn === pkg.code ? <Loader2 size={14} className="animate-spin" /> : 'Buy'}
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-text-muted">Ask an owner or admin to buy more credits.</p>
                )}
              </section>

              {/* Payment history */}
              <section className="bg-white rounded-xl border border-border overflow-hidden">
                <div className="flex items-center gap-2 px-6 py-4 border-b border-border">
                  <Receipt size={16} className="text-brand-blue" />
                  <h2 className="font-semibold text-text text-sm">Payment history</h2>
                </div>
                {payments.length === 0 ? (
                  <p className="text-sm text-text-muted text-center py-10">No payments yet.</p>
                ) : (
                  <ul>
                    {payments.map((p) => (
                      <li key={p.provider_reference ?? `${p.purpose}-${p.paid_at}`} className="flex items-center justify-between gap-3 px-6 py-3 border-b border-border last:border-0">
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-text truncate">
                            {p.purpose.replace(/_/g, ' ')}
                          </p>
                          <p className="text-xs text-text-muted">
                            {p.paid_at ? formatDate(p.paid_at) : 'Not yet paid'}
                          </p>
                        </div>
                        <div className="flex items-center gap-3 flex-shrink-0">
                          <span className="text-sm text-text">{formatPrice(p.amount_kobo, p.currency)}</span>
                          <PaymentStatusBadge status={p.status} />
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}
        </div>
      </main>

      <Footer />
    </div>
  )
}
