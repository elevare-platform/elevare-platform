import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

// ─── Options ─────────────────────────────────────────────────────────────────

const CONTRACT_TYPE_OPTIONS = [
  { value: '', label: 'All Contract Types' },
  { value: 'FULL_TIME', label: 'Full Time' },
  { value: 'PART_TIME', label: 'Part Time' },
  { value: 'CONTRACT', label: 'Contract' },
  { value: 'FREELANCE', label: 'Freelance' },
  { value: 'INTERNSHIP', label: 'Internship' },
]

const WORK_MODEL_OPTIONS = [
  { value: '', label: 'All Work Models' },
  { value: 'REMOTE', label: 'Remote' },
  { value: 'HYBRID', label: 'Hybrid' },
  { value: 'ONSITE', label: 'Onsite' },
]

const INDUSTRY_OPTIONS = [
  { value: '', label: 'All Industries' },
  { value: 'technology', label: 'Technology' },
  { value: 'finance', label: 'Finance & Banking' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'education', label: 'Education' },
  { value: 'marketing', label: 'Marketing & Media' },
  { value: 'engineering', label: 'Engineering' },
  { value: 'legal', label: 'Legal' },
  { value: 'logistics', label: 'Logistics & Supply Chain' },
  { value: 'hospitality', label: 'Hospitality & Tourism' },
  { value: 'other', label: 'Other' },
]

const POSTED_TIME_OPTIONS = [
  { value: '', label: 'Any Time' },
  { value: '1', label: 'Last 24 hours' },
  { value: '7', label: 'Last 7 days' },
  { value: '14', label: 'Last 14 days' },
  { value: '30', label: 'Last 30 days' },
]

// Experience level pills
const EXPERIENCE_LEVELS = [
  { value: 'none', label: 'No Experience' },
  { value: '1', label: '1 Year' },
  { value: '2', label: '2 Years' },
  { value: '3', label: '3 Years' },
  { value: '5', label: '5 Years' },
  { value: '7', label: '7 Years' },
  { value: '10', label: '10+ Years' },
]

// ─── Shared sub-components ────────────────────────────────────────────────────

function SectionLabel({ children }) {
  return (
    <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
      {children}
    </p>
  )
}

function FilterSelect({ id, label, value, options, onChange }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs font-medium text-text-muted uppercase tracking-wide">
        {label}
      </label>
      <div className="relative">
        <select
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            'w-full appearance-none rounded-lg border border-border bg-surface',
            'pl-3 pr-9 py-2.5 text-sm text-text leading-tight truncate',
            'cursor-pointer transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue',
            value && 'border-brand-blue/40 bg-brand-blue-light/30 text-brand-blue font-medium'
          )}
        >
          {options.map(({ value: v, label: l }) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
        <ChevronDown
          size={15}
          className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted"
          aria-hidden="true"
        />
      </div>
    </div>
  )
}

/**
 * ExperiencePills — selectable pill buttons for experience level.
 * Selecting an active pill deactivates it (sets to null).
 */
function ExperiencePills({ value, onChange }) {
  return (
    <div>
      <SectionLabel>Experience Level</SectionLabel>
      <div className="flex flex-wrap gap-2">
        {EXPERIENCE_LEVELS.map(({ value: v, label }) => {
          const isActive = value === v
          return (
            <button
              key={v}
              type="button"
              onClick={() => onChange(isActive ? null : v)}
              aria-pressed={isActive}
              className={cn(
                'inline-flex items-center justify-center h-7 px-3 rounded-full text-xs font-medium',
                'whitespace-nowrap transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue',
                isActive
                  ? 'bg-brand-blue text-white'
                  : 'border border-border text-text-muted hover:border-brand-blue hover:text-brand-blue bg-surface'
              )}
            >
              {label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ─── JobFilters ───────────────────────────────────────────────────────────────

/**
 * JobFilters — contract type, work model, industry, posted time, and
 * experience level filters.
 *
 * @param {Object} props
 * @param {Object} props.filters - Current filter state
 * @param {Function} props.onChange - Called with updated filter object
 */
export function JobFilters({ filters = {}, onChange }) {
  const set = (key, val) => onChange({ ...filters, [key]: val || undefined })

  return (
    <div className="flex flex-col gap-5">
      <FilterSelect
        id="filter-contract-type"
        label="Job Type"
        value={filters.contract_type ?? ''}
        options={CONTRACT_TYPE_OPTIONS}
        onChange={(val) => set('contract_type', val)}
      />

      <FilterSelect
        id="filter-work-model"
        label="Work Model"
        value={filters.work_model ?? ''}
        options={WORK_MODEL_OPTIONS}
        onChange={(val) => set('work_model', val)}
      />

      <FilterSelect
        id="filter-industry"
        label="Industry"
        value={filters.industry ?? ''}
        options={INDUSTRY_OPTIONS}
        onChange={(val) => set('industry', val)}
      />

      <FilterSelect
        id="filter-posted-time"
        label="Posted"
        value={filters.posted_days ?? ''}
        options={POSTED_TIME_OPTIONS}
        onChange={(val) => set('posted_days', val)}
      />

      <ExperiencePills
        value={filters.experience_level ?? null}
        onChange={(val) => onChange({ ...filters, experience_level: val ?? undefined })}
      />
    </div>
  )
}
