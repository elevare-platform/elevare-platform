import { useState } from 'react'
import { CalendarCheck, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * InterviewListButton - "add to this job's interview list" toggle.
 * Distinct from SaveHeartButton (global bookmark, no job)  -  this is
 * per-job, the queue-for-interview stage ahead of Shortlist.
 */
export default function InterviewListButton({ onList, onToggle, className }) {
  const [busy, setBusy] = useState(false)

  const handleClick = async (e) => {
    e.stopPropagation()
    if (busy) return
    setBusy(true)
    try {
      await onToggle()
    } finally {
      setBusy(false)
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      aria-label={onList ? 'Remove from interview list' : 'Add to interview list'}
      title={onList ? 'On interview list' : 'Add to interview list'}
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors flex-shrink-0',
        onList
          ? 'bg-violet-50 border-violet-200 text-violet-700'
          : 'border-border text-text-muted hover:text-violet-600 hover:border-violet-200',
        className
      )}
    >
      {busy ? <Loader2 size={13} className="animate-spin" /> : <CalendarCheck size={13} />}
      {onList ? 'On interview list' : 'Interview list'}
    </button>
  )
}
