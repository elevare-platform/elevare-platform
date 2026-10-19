import { History, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useCreditHistory } from '@/hooks/useCreditHistory'
import { describeChange } from '@/lib/creditHistory'
import { cn } from '@/lib/utils'

function formatWhen(isoString) {
  return new Date(isoString).toLocaleString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

/**
 * Where an organization's credits went: every pack, monthly plan credit, spend and
 * refund, newest first, with which pot (plan or bought credits) each one moved.
 */
export default function CreditHistory() {
  const { items, hasMore, loading, loadingMore, error, loadMore, reload } = useCreditHistory()

  return (
    <section className="bg-white rounded-xl border border-border overflow-hidden">
      <div className="flex items-center gap-2 px-6 py-4 border-b border-border">
        <History size={16} className="text-brand-blue" />
        <h2 className="font-semibold text-text text-sm">Credit history</h2>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-10 text-text-muted">
          <Loader2 size={18} className="animate-spin" />
        </div>
      ) : error && items.length === 0 ? (
        <div className="px-6 py-8 text-center">
          <p className="text-sm text-red-600">{error}</p>
          <Button size="sm" variant="outline" className="mt-3" onClick={reload}>Try again</Button>
        </div>
      ) : items.length === 0 ? (
        <p className="px-6 py-8 text-sm text-text-muted text-center">
          No credit activity yet. Credits you receive and spend will appear here.
        </p>
      ) : (
        <>
          <ul className="divide-y divide-border">
            {items.map((item) => {
              const { amount, tone, source } = describeChange(item)
              return (
                <li key={item.id} className="flex items-start justify-between gap-4 px-6 py-3">
                  <div className="min-w-0">
                    <p className="text-sm text-text">{item.description}</p>
                    {item.detail && (
                      <p className="text-xs text-text-muted truncate">{item.detail}</p>
                    )}
                    <p className="text-[11px] text-text-muted mt-0.5">{formatWhen(item.created_at)}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p
                      className={cn(
                        'text-sm font-semibold',
                        tone === 'in' ? 'text-green-700' : 'text-text',
                      )}
                    >
                      {amount}
                    </p>
                    {source && <p className="text-[11px] text-text-muted">{source}</p>}
                  </div>
                </li>
              )
            })}
          </ul>

          {error && <p className="px-6 pt-3 text-xs text-red-600">{error}</p>}
          {hasMore && (
            <div className="px-6 py-4 border-t border-border text-center">
              <Button size="sm" variant="outline" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? <Loader2 size={14} className="animate-spin" /> : 'Load more'}
              </Button>
            </div>
          )}
        </>
      )}
    </section>
  )
}
