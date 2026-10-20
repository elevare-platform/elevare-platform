import { RefreshCw, X } from 'lucide-react'
import { describeRescore } from '@/lib/rescore'
import { cn } from '@/lib/utils'

/**
 * The strip above a job's candidates when some of them have no usable score: their CV
 * could not be read, or scoring did not complete. Rescore reads unreadable CVs again
 * and scores everyone who needs it, a batch at a time. After a press it says what it
 * did, in the server's counts.
 */
export default function RescoreBar({ status, working, result, onRescore, onDismissResult }) {
  const waiting = status?.total ?? 0
  if (waiting === 0 && !result) return null

  return (
    <div
      role="region"
      aria-label="Rescore candidates"
      className={cn(
        'mb-6 rounded-xl border p-4 flex flex-wrap items-start justify-between gap-3',
        waiting > 0 ? 'border-brand-amber/30 bg-brand-amber/5' : 'border-green-200 bg-green-50',
      )}
    >
      <div className="min-w-0 flex-1 space-y-1">
        {waiting > 0 && (
          <>
            <p className="text-sm font-medium text-amber-800">
              {waiting} {waiting === 1 ? 'candidate has' : 'candidates have'} no score
            </p>
            <p className="text-xs text-amber-700">
              Their CV could not be read, or scoring did not complete. Rescore reads those CVs again and
              scores them. It starts up to 25 at a time.
            </p>
          </>
        )}
        {result && (
          <p role="status" className={cn('text-xs', waiting > 0 ? 'text-amber-800' : 'text-green-800')}>
            {describeRescore(result)}
            {waiting === 0 && ' Scores appear here as they finish; refresh in a minute.'}
          </p>
        )}
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        {waiting > 0 && (
          <button
            type="button"
            onClick={() => onRescore({})}
            disabled={working}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-brand-amber text-brand-amber hover:bg-brand-amber hover:text-white transition-colors disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw size={13} className={working ? 'animate-spin' : ''} />
            {working ? 'Starting…' : 'Rescore'}
          </button>
        )}
        {result && (
          <button
            type="button"
            onClick={onDismissResult}
            aria-label="Hide this message"
            className="p-1 text-text-muted hover:text-text rounded cursor-pointer"
          >
            <X size={14} />
          </button>
        )}
      </div>
    </div>
  )
}
