function formatUsd(value) {
  return value.toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  })
}

/**
 * CostCard - like StatCard but currency-aware, and distinguishes "$0.00"
 * (genuinely no cost) from "price not configured" (calls happened but the
 * model isn't in app/core/ai_pricing.py yet) - collapsing those into the
 * same $0.00 would hide real, billed usage with unknown cost.
 */
export default function CostCard({ label, costUsd, calls, icon: Icon }) {
  const unpriced = costUsd == null && calls > 0

  return (
    <div className="bg-white rounded-xl border border-border p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-text-muted font-medium">{label}</p>
        {Icon && <Icon size={18} className="text-text-muted" aria-hidden="true" />}
      </div>

      {unpriced ? (
        <div>
          <p className="text-2xl font-bold text-amber-600">Unknown</p>
          <p className="text-xs text-amber-600 mt-1">
            Price not configured for this model. See app/core/ai_pricing.py
          </p>
        </div>
      ) : (
        <p className="text-3xl font-bold text-text tabular-nums">
          {formatUsd(costUsd ?? 0)}
        </p>
      )}

      <p className="text-xs text-text-muted">
        {calls?.toLocaleString() ?? 0} call{calls === 1 ? '' : 's'} this month
      </p>
    </div>
  )
}
