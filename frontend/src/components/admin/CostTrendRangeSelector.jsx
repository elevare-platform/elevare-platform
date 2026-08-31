const PRESETS = [
  { label: '3 months', months: 3 },
  { label: '6 months', months: 6 },
  { label: '12 months', months: 12 },
  { label: 'All time', months: null },
]

/**
 * Preset buttons (3/6/12 months, All time) plus a custom from/to date range.
 * Selecting a custom date clears the active preset and vice versa.
 */
export default function CostTrendRangeSelector({
  activePreset,
  onPresetChange,
  customFrom,
  customTo,
  onCustomChange,
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 mb-4">
      <div className="flex gap-1 bg-surface-muted rounded-lg p-1">
        {PRESETS.map((p) => (
          <button
            key={p.label}
            onClick={() => onPresetChange(p.months)}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
              activePreset === p.months && !customFrom && !customTo
                ? 'bg-white text-text shadow-sm'
                : 'text-text-muted hover:text-text'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2 text-xs text-text-muted">
        <label className="flex items-center gap-1">
          From
          <input
            type="date"
            value={customFrom ?? ''}
            onChange={(e) => onCustomChange({ from: e.target.value || undefined, to: customTo })}
            className="border border-border rounded-md px-2 py-1 text-xs"
          />
        </label>
        <label className="flex items-center gap-1">
          To
          <input
            type="date"
            value={customTo ?? ''}
            onChange={(e) => onCustomChange({ from: customFrom, to: e.target.value || undefined })}
            className="border border-border rounded-md px-2 py-1 text-xs"
          />
        </label>
      </div>
    </div>
  )
}
