import { cn } from '@/lib/utils'

// The "Not opened yet" tab on the Applicants and Pipeline tabs of a job, with how many there are
// (docs/08_DECISIONS.md, item 35). The count is always shown once there is one, so the employer
// is told without having to open the tab.
export default function NotOpenedTab({ selected, count, onClick }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={selected}
      data-testid="not-opened-tab"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors whitespace-nowrap flex-shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue',
        selected
          ? 'bg-brand-blue text-white'
          : 'bg-surface border border-border text-text-muted hover:text-text'
      )}
    >
      Not opened yet
      {count > 0 && (
        <span
          data-testid="not-opened-count"
          className={cn(
            'rounded-full px-1.5 text-[10px] font-semibold leading-4',
            selected ? 'bg-white/25 text-white' : 'bg-brand-blue text-white'
          )}
        >
          {count}
        </span>
      )}
    </button>
  )
}
