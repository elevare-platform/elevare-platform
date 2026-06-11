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

const SENIORITY_OPTIONS = [
  { value: '', label: 'All Levels' },
  { value: 'JUNIOR', label: 'Junior' },
  { value: 'MID', label: 'Mid-level' },
  { value: 'SENIOR', label: 'Senior' },
  { value: 'LEAD', label: 'Lead' },
  { value: 'EXECUTIVE', label: 'Executive' },
]

const POSTED_TIME_OPTIONS = [
  { value: '', label: 'Any Time' },
  { value: '1', label: 'Last 24 hours' },
  { value: '7', label: 'Last 7 days' },
  { value: '14', label: 'Last 14 days' },
  { value: '30', label: 'Last 30 days' },
]

const EXPERIENCE_OPTIONS = [
  { value: '', label: 'Any' },
  { value: '0', label: '0 (No experience)' },
  { value: '1', label: '1 year' },
  { value: '2', label: '2 years' },
  { value: '3', label: '3 years' },
  { value: '5', label: '5 years' },
  { value: '7', label: '7 years' },
  { value: '10', label: '10 years' },
  { value: '15', label: '15+ years' },
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
 * ExperienceRange — two selects for min and max years of experience.
 * Max defaults to "Any" when not set. If only max is set, it acts as a ceiling.
 * If both are set, it filters to a range.
 */
function ExperienceRange({ minValue, maxValue, onChange }) {
  const handleMin = (val) => onChange(val || undefined, maxValue)
  const handleMax = (val) => onChange(minValue, val || undefined)

  return (
    <div>
      <SectionLabel>Years of Experience</SectionLabel>
      <div className="flex items-center gap-2">
        <div className="flex-1 relative">
          <select
            id="exp-min"
            aria-label="Minimum years of experience"
            value={minValue ?? ''}
            onChange={(e) => handleMin(e.target.value)}
            className={cn(
              'w-full appearance-none rounded-lg border border-border bg-surface',
              'pl-3 pr-7 py-2 text-sm text-text leading-tight',
              'cursor-pointer transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue',
              minValue && 'border-brand-blue/40 text-brand-blue font-medium'
            )}
          >
            {EXPERIENCE_OPTIONS.map(({ value: v, label: l }) => (
              <option key={v} value={v}>{v === '' ? 'Min' : l}</option>
            ))}
          </select>
          <ChevronDown size={13} className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-text-muted" aria-hidden="true" />
        </div>

        <span className="text-xs text-text-muted flex-shrink-0">to</span>

        <div className="flex-1 relative">
          <select
            id="exp-max"
            aria-label="Maximum years of experience"
            value={maxValue ?? ''}
            onChange={(e) => handleMax(e.target.value)}
            className={cn(
              'w-full appearance-none rounded-lg border border-border bg-surface',
              'pl-3 pr-7 py-2 text-sm text-text leading-tight',
              'cursor-pointer transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue',
              maxValue && 'border-brand-blue/40 text-brand-blue font-medium'
            )}
          >
            {EXPERIENCE_OPTIONS.map(({ value: v, label: l }) => (
              <option key={v} value={v}>{v === '' ? 'Max' : l}</option>
            ))}
          </select>
          <ChevronDown size={13} className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-text-muted" aria-hidden="true" />
        </div>
      </div>
    </div>
  )
}

// ─── JobFilters ───────────────────────────────────────────────────────────────

/**
 * JobFilters — contract type, work model, seniority, posted time, and
 * experience range filters.
 *
 * @param {Object} props
 * @param {Object} props.filters - Current filter state
 * @param {Function} props.onChange - Called with updated filter object
 */
export function JobFilters({ filters = {}, onChange }) {
  const set = (key, val) => onChange({ ...filters, [key]: val || undefined })

  const handleExperienceChange = (min, max) => {
    onChange({
      ...filters,
      min_years_experience: min,
      max_years_experience: max,
    })
  }

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
        id="filter-seniority"
        label="Seniority Level"
        value={filters.seniority_level ?? ''}
        options={SENIORITY_OPTIONS}
        onChange={(val) => set('seniority_level', val)}
      />

      <FilterSelect
        id="filter-posted-time"
        label="Posted"
        value={filters.posted_days ?? ''}
        options={POSTED_TIME_OPTIONS}
        onChange={(val) => set('posted_days', val)}
      />

      <ExperienceRange
        minValue={filters.min_years_experience}
        maxValue={filters.max_years_experience}
        onChange={handleExperienceChange}
      />
    </div>
  )
}
