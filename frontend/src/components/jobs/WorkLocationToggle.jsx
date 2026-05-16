import { cn } from '@/lib/utils'

const PILLS = [
  { value: 'LOCAL', label: 'Local' },
  { value: 'INTERNATIONAL', label: 'International' },
]

/**
 * WorkLocationToggle — LOCAL / INTERNATIONAL pill toggle.
 * Pills maintain consistent height and handle long text without overflow.
 *
 * @param {Object} props
 * @param {null|'LOCAL'|'INTERNATIONAL'} props.value
 * @param {Function} props.onChange
 */
export function WorkLocationToggle({ value, onChange }) {
  const handleClick = (pill) => {
    onChange(value === pill ? null : pill)
  }

  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Work location filter">
      {PILLS.map(({ value: pill, label }) => {
        const isActive = value === pill
        return (
          <button
            key={pill}
            type="button"
            onClick={() => handleClick(pill)}
            aria-pressed={isActive}
            className={cn(
              // Fixed height, horizontal padding, no text wrapping
              'inline-flex items-center justify-center h-8 px-4 rounded-full',
              'text-xs font-semibold whitespace-nowrap',
              // Overflow protection for very long labels
              'max-w-[160px] overflow-hidden text-ellipsis',
              'transition-all duration-150',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-amber focus-visible:ring-offset-1',
              isActive
                ? 'bg-brand-amber text-white shadow-sm'
                : 'border border-slate-200 text-slate-500 bg-white hover:border-brand-amber hover:text-brand-amber',
            )}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
