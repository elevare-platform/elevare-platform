import { useState } from 'react'
import { Heart, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * SaveHeartButton - the global "save candidate" bookmark toggle, reused
 * across candidate search results, AI talent matches, and applicants.
 * Instant toggle, no confirmation  -  this is a lightweight, reversible
 * bookmark, not a credit-costing or candidate-facing action.
 */
export default function SaveHeartButton({ saved, onToggle, className }) {
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
      aria-label={saved ? 'Remove from saved candidates' : 'Save candidate'}
      title={saved ? 'Saved' : 'Save candidate'}
      className={cn(
        'inline-flex items-center justify-center w-8 h-8 rounded-full border transition-colors flex-shrink-0',
        saved
          ? 'bg-red-50 border-red-200 text-red-500'
          : 'border-border text-text-muted hover:text-red-500 hover:border-red-200',
        className
      )}
    >
      {busy ? (
        <Loader2 size={14} className="animate-spin" />
      ) : (
        <Heart size={14} className={saved ? 'fill-current' : ''} />
      )}
    </button>
  )
}
