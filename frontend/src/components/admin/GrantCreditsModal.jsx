import { useState } from 'react'
import { Coins, Loader2, CheckCircle2 } from 'lucide-react'
import { useAdmin } from '@/hooks/useAdmin'

export default function GrantCreditsModal({ employer, onClose, onGranted }) {
  const { grantEmployerCredits } = useAdmin()
  const [amount, setAmount] = useState(10)
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null) // { balance }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!amount || amount < 1) {
      setError('Enter an amount of at least 1 credit')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const data = await grantEmployerCredits(employer.id, Number(amount), reason || undefined)
      setResult(data)
      onGranted?.(data)
    } catch (err) {
      setError(err.response?.data?.message ?? 'Failed to grant credits')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl max-w-sm w-full p-6 space-y-4">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-full bg-brand-blue/10 flex items-center justify-center flex-shrink-0">
            <Coins size={16} className="text-brand-blue" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-text">Grant credits</h2>
            <p className="text-sm text-text-muted mt-1">
              {employer.first_name} {employer.last_name} <span className="text-text-muted">({employer.email})</span>
            </p>
          </div>
        </div>

        {result ? (
          <div className="rounded-lg bg-green-50 border border-green-200 p-4 flex items-start gap-2">
            <CheckCircle2 size={16} className="text-green-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-green-800">
              Granted. New balance: <span className="font-semibold">{result.balance} credits</span>.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs font-medium text-text-muted block mb-1">Amount</label>
              <input
                type="number"
                min={1}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue"
                autoFocus
              />
            </div>
            <div>
              <label className="text-xs font-medium text-text-muted block mb-1">
                Reason <span className="text-text-muted">(optional)</span>
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
                maxLength={200}
                placeholder="e.g. Pilot program top-up"
                className="w-full text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue resize-none"
              />
            </div>

            {error && <p className="text-xs text-red-600">{error}</p>}

            <div className="flex gap-3 justify-end pt-1">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm rounded-lg border border-border hover:bg-surface-muted transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2 text-sm rounded-lg font-medium bg-brand-blue text-white hover:opacity-90 transition-colors disabled:opacity-50 inline-flex items-center gap-2"
              >
                {submitting && <Loader2 size={14} className="animate-spin" />}
                Grant credits
              </button>
            </div>
          </form>
        )}

        {result && (
          <div className="flex justify-end pt-1">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm rounded-lg font-medium bg-brand-blue text-white hover:opacity-90 transition-colors"
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
