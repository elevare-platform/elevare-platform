import { ageInDays, cn, timeAgo } from '@/lib/utils'
import { DEFAULT_MIN_SCORE } from '@/hooks/useTalentPoolFilters'

// Shared by the standalone Talent Pool page and the Talent Pipeline tab on the
// job's Applicants page (state lives in useTalentPoolFilters).

const RECENCY_OPTIONS = [
  { value: '', label: 'Any time' },
  { value: '7', label: 'Added in last 7 days' },
  { value: '14', label: 'Added in last 14 days' },
  { value: '30', label: 'Added in last 30 days' },
]

const SELECT_CLASS =
  'text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue'

export function TalentPoolFilterControls({ filters, hasJob }) {
  const { sortBy, setSortBy, recency, setRecency, minScoreInput, setMinScoreInput } = filters
  const chipOn = minScoreInput === String(DEFAULT_MIN_SCORE)

  return (
    <>
      {hasJob && (
        <select value={sortBy} onChange={e => setSortBy(e.target.value)} aria-label="Sort by" className={SELECT_CLASS}>
          <option value="score">Best match first</option>
          <option value="newest">Newest first</option>
        </select>
      )}
      <select value={recency} onChange={e => setRecency(e.target.value)} aria-label="Added within" className={SELECT_CLASS}>
        {RECENCY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      {hasJob && (
        <div className="flex items-center gap-1">
          <input type="number" min="0" max="100" inputMode="numeric"
            value={minScoreInput} onChange={e => setMinScoreInput(e.target.value)}
            placeholder="Min score" aria-label="Minimum score"
            className={cn(SELECT_CLASS, 'w-24')} />
          <button type="button"
            onClick={() => setMinScoreInput(chipOn ? '' : String(DEFAULT_MIN_SCORE))}
            aria-pressed={chipOn}
            className={cn(
              'text-xs font-semibold rounded-full border px-2.5 py-1.5 transition-colors',
              chipOn
                ? 'bg-brand-blue text-white border-brand-blue'
                : 'bg-white text-text-muted border-border hover:text-text'
            )}>
            {DEFAULT_MIN_SCORE}+
          </button>
        </div>
      )}
    </>
  )
}

// Candidates with no score yet can never satisfy "at least N", so say so, or a
// CV that is still being scored looks like it failed to upload.
export function MinScoreNote({ filters, hasJob }) {
  if (!hasJob || filters.minScore === '') return null
  return (
    <p className="text-xs text-text-muted">
      Showing candidates scoring {filters.minScore} or higher. Candidates still being scored are hidden until their score is ready.
    </p>
  )
}

const FRESH_DAYS = 7 // added this week: stands out so a new batch is visible in a score-sorted list
const STALE_DAYS = 28 // older than a month: likely already worked through

const AGE_TONE = {
  fresh: 'rounded-full border border-green-200 bg-green-50 px-2 py-0.5 text-green-700',
  normal: 'text-text-muted',
  stale: 'rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-amber-700',
}

// "NEW Added 3d ago · Scored 2d ago": the list stays sorted by score, so age
// has to be visible on the row itself. Colour is only a hint; the words carry
// the meaning. Clients don't maintain statuses, so age is the one signal we
// can always show.
export function AgeLabel({ profile, verb = 'Added' }) {
  const added = timeAgo(profile.created_at)
  const scored = profile.ai_score != null ? timeAgo(profile.ai_score_computed_at) : null
  if (!added) return null
  const ageDays = ageInDays(profile.created_at)
  const tone = ageDays <= FRESH_DAYS ? 'fresh' : ageDays > STALE_DAYS ? 'stale' : 'normal'
  return (
    <p
      data-age={tone}
      className={cn('mt-0.5 inline-flex items-center gap-1.5 text-[11px]', AGE_TONE[tone])}
      title={`${verb} ${new Date(profile.created_at).toLocaleString('en-GB')}`}
    >
      {tone === 'fresh' && <span className="font-bold uppercase tracking-wide">New</span>}
      {verb} {added}{scored && ` · Scored ${scored}`}
    </p>
  )
}
