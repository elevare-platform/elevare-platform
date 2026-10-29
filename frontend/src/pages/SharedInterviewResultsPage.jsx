import { useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { Search } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import { BAND_STYLE } from '@/lib/scoringProfile'
import { STATUS, hasDetail, scoreColour } from '@/lib/sharedResults'
import SharedCandidateDetail from '@/components/employer/SharedCandidateDetail'
import ReviewedTag from '@/components/employer/ReviewedTag'

// Why a link does not open, by the error code the server sends.
const LINK_PROBLEMS = {
  SHARE_LINK_EXPIRED: {
    title: 'This link has expired',
    text: 'Links stop working after 3 days. Please ask for a new one.',
  },
  SHARE_LINK_REVOKED: {
    title: 'This link is no longer active',
    text: 'It was replaced or withdrawn. Please ask for the latest link.',
  },
  SHARE_LINK_NOT_FOUND: {
    title: 'This link is not valid',
    text: 'It may have been copied incompletely. Please ask for a new one.',
  },
}

// A search box only helps once the list is long enough to lose someone in.
const SEARCH_FROM = 6

const SORTS = [
  { value: 'order', label: 'Order on the list' },
  { value: 'interview', label: 'Interview score' },
  { value: 'weighted', label: 'Weighted score' },
  { value: 'cv', label: 'CV score' },
]

const SORT_KEY = {
  interview: (c) => c.interview_score,
  weighted: (c) => (c.score_report?.complete ? c.score_report.score : null),
  cv: (c) => c.cv_score,
}

function formatDate(iso, options) {
  return iso ? new Date(iso).toLocaleDateString('en-GB', options) : null
}

function ScoreChip({ label, score }) {
  if (score == null) return null
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold', scoreColour(score))}>
      <span className="font-medium opacity-80">{label}</span> {score}
    </span>
  )
}

// One line of the list: enough to compare candidates without opening any of them.
function CandidateRow({ entry, selected, onSelect }) {
  const { candidate, rank } = entry
  const status = STATUS[candidate.status] ?? STATUS.NOT_INVITED
  const report = candidate.score_report
  const openable = hasDetail(candidate)

  const body = (
    <>
      <span className="w-7 h-7 rounded-full bg-surface-muted text-text-muted text-xs font-semibold flex items-center justify-center flex-shrink-0">
        {rank}
      </span>
      <span className="flex-1 min-w-0">
        <span className="block font-semibold text-text text-sm break-words">{candidate.name}</span>
        {candidate.current_title && (
          <span className="block text-xs text-text-muted line-clamp-1">{candidate.current_title}</span>
        )}
        <span className="flex flex-wrap items-center gap-1.5 mt-1">
          <span className={cn('inline-block px-2 py-0.5 rounded-full border text-[11px] font-medium', status.className)}>
            {status.label}
          </span>
          {candidate.status === 'COMPLETED' && <ScoreChip label="Interview" score={candidate.interview_score} />}
          <ScoreChip label="CV" score={candidate.cv_score} />
          {report?.complete && (
            <span className={cn('inline-block px-2 py-0.5 rounded-full border text-[11px] font-medium', BAND_STYLE[report.band])}>
              {report.band}
            </span>
          )}
          {(candidate.interview_reviewed || report?.reviewed) && <ReviewedTag />}
        </span>
      </span>
    </>
  )

  if (!openable) {
    return <li className="flex items-center gap-3 rounded-xl border border-border bg-white p-3 opacity-80">{body}</li>
  }
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-current={selected ? 'true' : undefined}
        aria-label={`${rank}. ${candidate.name}`}
        className={cn(
          'w-full flex items-center gap-3 rounded-xl border bg-white p-3 text-left transition-colors',
          selected ? 'border-brand-blue ring-2 ring-brand-blue/20' : 'border-border hover:border-brand-blue/40',
        )}
      >
        {body}
      </button>
    </li>
  )
}

function Message({ title, text }) {
  return (
    <div className="min-h-screen bg-surface-muted flex items-center justify-center px-4">
      <div className="text-center max-w-sm">
        <p className="text-2xl font-bold text-text mb-2">{title}</p>
        <p className="text-sm text-text-muted">{text}</p>
      </div>
    </div>
  )
}

/**
 * The page behind a job's "interview results" link: read-only, no login. A list of every
 * candidate on the job's interview list, to compare and sort, and one candidate at a time
 * beside it with the recording, the interview and CV assessments, the questions the AI asked and
 * the conversation. The chosen candidate is kept in the address (`?c=3`), so a panel member can
 * send a colleague straight to someone.
 */
export default function SharedInterviewResultsPage() {
  const { token } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState(null)
  const [problem, setProblem] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showAllFocus, setShowAllFocus] = useState(false)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sort, setSort] = useState('order')
  // On a phone the list and the candidate take turns; on a wide screen they sit side by side.
  const [detailOpen, setDetailOpen] = useState(() => searchParams.has('c'))

  useEffect(() => {
    let cancelled = false
    api.get(`/api/v1/public/interview-results/${token}`)
      .then(({ data: body }) => { if (!cancelled) setData(body) })
      .catch((err) => {
        if (cancelled) return
        const code = err.response?.data?.code
        setProblem(
          LINK_PROBLEMS[code] ?? {
            title: 'Something went wrong',
            text: 'We could not load these results. Please try again in a moment.',
          },
        )
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [token])

  // Each candidate keeps the number they have on the list, however the list is sorted or filtered.
  const entries = useMemo(
    () => (data?.candidates ?? []).map((candidate, i) => ({ candidate, rank: i + 1 })),
    [data],
  )

  const statusCounts = useMemo(() => {
    const counts = {}
    entries.forEach(({ candidate }) => { counts[candidate.status] = (counts[candidate.status] ?? 0) + 1 })
    return counts
  }, [entries])

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase()
    let list = entries.filter(({ candidate }) =>
      (statusFilter === 'all' || candidate.status === statusFilter) &&
      (!needle || candidate.name.toLowerCase().includes(needle)),
    )
    const key = SORT_KEY[sort]
    if (key) {
      // Highest first, and anyone without that score after everyone who has one.
      list = [...list].sort((a, b) => {
        const x = key(a.candidate)
        const y = key(b.candidate)
        if (x == null && y == null) return 0
        if (x == null) return 1
        if (y == null) return -1
        return y - x
      })
    }
    return list
  }, [entries, search, statusFilter, sort])

  const noIndex = (
    <Helmet>
      <title>Interview results | Elevare Human Solutions</title>
      {/* Personal data and recordings: never for search engines. */}
      <meta name="robots" content="noindex, nofollow" />
    </Helmet>
  )

  if (loading) {
    return (
      <div className="min-h-screen bg-surface-muted flex items-center justify-center">
        {noIndex}
        <div className="w-8 h-8 border-4 border-brand-blue border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (problem) {
    return (
      <>
        {noIndex}
        <Message title={problem.title} text={problem.text} />
      </>
    )
  }

  // The candidate in the address if there is one to open, else the first finished interview, else
  // the first anyone can open.
  const asked = Number(searchParams.get('c'))
  const requested = entries.find(({ rank, candidate }) => rank === asked && hasDetail(candidate))
  const selected =
    requested ??
    entries.find(({ candidate }) => candidate.status === 'COMPLETED') ??
    entries.find(({ candidate }) => hasDetail(candidate)) ??
    null

  const openable = visible.filter(({ candidate }) => hasDetail(candidate))
  const at = selected ? openable.findIndex((entry) => entry.rank === selected.rank) : -1

  const choose = (entry) => {
    setSearchParams({ c: String(entry.rank) }, { replace: true })
    setDetailOpen(true)
  }

  const expiry = formatDate(data.expires_at, { day: 'numeric', month: 'long', year: 'numeric' })
  const focus = data.interview_focus ?? ''
  const longFocus = focus.length > 400
  const statusChips = [
    { value: 'all', label: 'All', count: entries.length },
    ...Object.keys(STATUS)
      .filter((value) => statusCounts[value])
      .map((value) => ({ value, label: STATUS[value].label, count: statusCounts[value] })),
  ]

  return (
    <div className="min-h-screen bg-surface-muted">
      {noIndex}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-6">
        <div className="space-y-1">
          <p className="text-xs font-semibold text-text-muted">Interview results</p>
          <h1 className="text-2xl font-bold text-text font-sans">{data.job_title}</h1>
          {data.company_name && <p className="text-sm text-text-muted">{data.company_name}</p>}
          <p className="text-xs text-text-muted">
            {data.completed_count} of {data.total_candidates} interviews completed
            {expiry && <> · This link expires on {expiry}</>}
          </p>
        </div>

        {focus && (
          <div className="rounded-xl border border-border bg-white p-4">
            <h2 className="text-sm font-semibold text-text mb-1">What the interview was set to cover</h2>
            <p className={cn('text-sm text-text whitespace-pre-wrap', longFocus && !showAllFocus && 'line-clamp-4')}>
              {focus}
            </p>
            {longFocus && (
              <button
                type="button"
                onClick={() => setShowAllFocus((v) => !v)}
                className="text-xs text-brand-blue hover:underline mt-1"
              >
                {showAllFocus ? 'Show less' : 'Show all'}
              </button>
            )}
          </div>
        )}

        {entries.length === 0 ? (
          <p className="text-sm text-text-muted text-center py-10">No candidates on this interview list yet.</p>
        ) : (
          <div className="grid gap-6 lg:grid-cols-[22rem_minmax(0,1fr)] lg:items-start">
            <div className={cn('space-y-3', detailOpen && 'hidden lg:block')}>
              <div className="space-y-2">
                <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-1.5">
                  {statusChips.length > 2 && statusChips.map((chip) => (
                    <button
                      key={chip.value}
                      type="button"
                      aria-pressed={statusFilter === chip.value}
                      onClick={() => setStatusFilter(chip.value)}
                      className={cn(
                        'px-3 py-1.5 rounded-full text-xs font-semibold transition-colors',
                        statusFilter === chip.value
                          ? 'bg-brand-blue text-white'
                          : 'bg-white border border-border text-text-muted hover:text-text',
                      )}
                    >
                      {chip.label} ({chip.count})
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2">
                  {entries.length >= SEARCH_FROM && (
                    <div className="relative flex-1 min-w-0">
                      <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" aria-hidden="true" />
                      <input
                        type="search"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search by name"
                        aria-label="Search candidates by name"
                        className="w-full pl-8 pr-3 py-2 text-sm rounded-lg border border-border bg-white focus:outline-none focus:ring-2 focus:ring-brand-blue"
                      />
                    </div>
                  )}
                  <select
                    value={sort}
                    onChange={(e) => setSort(e.target.value)}
                    aria-label="Sort candidates by"
                    className="py-2 pl-2 pr-6 text-sm rounded-lg border border-border bg-white focus:outline-none focus:ring-2 focus:ring-brand-blue"
                  >
                    {SORTS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </div>
              </div>

              {visible.length === 0 ? (
                <p className="text-sm text-text-muted text-center py-8">No candidate matches this search.</p>
              ) : (
                <ul aria-label="Candidates" className="space-y-2 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto lg:pr-1">
                  {visible.map((entry) => (
                    <CandidateRow
                      key={entry.rank}
                      entry={entry}
                      selected={selected?.rank === entry.rank}
                      onSelect={() => choose(entry)}
                    />
                  ))}
                </ul>
              )}
            </div>

            <div className={cn(!detailOpen && 'hidden lg:block')}>
              {selected ? (
                <SharedCandidateDetail
                  key={selected.rank}
                  candidate={selected.candidate}
                  rank={selected.rank}
                  position={at >= 0 ? { index: at + 1, total: openable.length } : null}
                  onPrevious={at > 0 ? () => choose(openable[at - 1]) : null}
                  onNext={at >= 0 && at < openable.length - 1 ? () => choose(openable[at + 1]) : null}
                  onBack={() => setDetailOpen(false)}
                />
              ) : (
                <p className="rounded-xl border border-dashed border-border bg-white p-8 text-center text-sm text-text-muted">
                  There is nothing to open yet. A candidate appears here once the interview is done.
                </p>
              )}
            </div>
          </div>
        )}

        {data.truncated && (
          <p className="text-xs text-text-muted text-center">
            Showing the first {data.candidates.length} of {data.total_candidates} candidates.
          </p>
        )}

        <p className="text-xs text-text-muted text-center pt-4">
          This page contains personal information and recordings shared for hiring purposes. Please
          do not forward it.
        </p>
        <p className="text-xs text-text-muted text-center">Powered by Elevare Human Solutions</p>
      </div>
    </div>
  )
}
