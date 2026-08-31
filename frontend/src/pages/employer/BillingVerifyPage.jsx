import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CheckCircle2, XCircle, Loader2, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useBilling } from '@/hooks/useBilling'
import ehsLogo from '@/assets/ehs-logo.png'

/**
 * BillingVerifyPage - /employer/billing/verify
 * Where Paystack redirects back to after checkout (see the callback_url
 * set server-side in PaystackAdapter.create_checkout_session). Paystack
 * appends ?reference=...&trxref=... itself - we don't construct it.
 */
export default function BillingVerifyPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { verifyCheckout } = useBilling()
  const [status, setStatus] = useState('loading') // loading | succeeded | pending | failed | error
  const [message, setMessage] = useState(null)

  useEffect(() => {
    const reference = searchParams.get('reference') ?? searchParams.get('trxref')
    if (!reference) {
      setStatus('error')
      setMessage('No payment reference found.')
      return
    }

    let cancelled = false
    verifyCheckout(reference)
      .then((payment) => {
        if (cancelled) return
        if (payment.status === 'SUCCEEDED') setStatus('succeeded')
        else if (payment.status === 'PENDING') setStatus('pending')
        else setStatus('failed')
      })
      .catch((err) => {
        if (cancelled) return
        setStatus('error')
        setMessage(err.response?.data?.message ?? 'Could not verify this payment.')
      })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="min-h-screen bg-surface-muted flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <img src={ehsLogo} alt="Elevare" className="h-9 w-auto" />
        </div>

        <div className="bg-white rounded-2xl border border-border p-8 shadow-sm text-center space-y-4">
          {status === 'loading' && (
            <>
              <Loader2 size={40} className="mx-auto text-brand-blue animate-spin" />
              <p className="text-text font-medium">Confirming your payment…</p>
            </>
          )}

          {status === 'succeeded' && (
            <>
              <CheckCircle2 size={40} className="mx-auto text-green-500" />
              <h1 className="text-xl font-bold text-text">Payment successful</h1>
              <p className="text-sm text-text-muted">Your account has been updated.</p>
              <Button onClick={() => navigate('/employer/billing')} className="w-full">
                Back to Billing
              </Button>
            </>
          )}

          {status === 'pending' && (
            <>
              <Clock size={40} className="mx-auto text-amber-500" />
              <h1 className="text-xl font-bold text-text">Still confirming</h1>
              <p className="text-sm text-text-muted">
                Paystack hasn't confirmed this payment yet. It will update automatically shortly. Check back on your billing page.
              </p>
              <Button onClick={() => navigate('/employer/billing')} className="w-full">
                Back to Billing
              </Button>
            </>
          )}

          {(status === 'failed' || status === 'error') && (
            <>
              <XCircle size={40} className="mx-auto text-red-500" />
              <h1 className="text-xl font-bold text-text">
                {status === 'failed' ? "Payment didn't go through" : "Couldn't confirm payment"}
              </h1>
              <p className="text-sm text-text-muted">
                {message ?? 'No charge was completed. You can try again from your billing page.'}
              </p>
              <Button onClick={() => navigate('/employer/billing')} className="w-full">
                Back to Billing
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
