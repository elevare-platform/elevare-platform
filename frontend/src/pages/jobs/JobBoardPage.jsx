import { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import { Helmet } from 'react-helmet-async'
import {
  SlidersHorizontal, X, Briefcase, MapPin, Search,
  ChevronDown, ArrowUpDown, SearchX,
} from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { JobCard } from '@/components/jobs/JobCard'
import { JobFilters } from '@/components/jobs/JobFilters'
import { WorkLocationToggle } from '@/components/jobs/WorkLocationToggle'
import { SalaryRangeSlider, SALARY_MIN, SALARY_MAX } from '@/components/jobs/SalaryRangeSlider'
import { useJobs } from '@/hooks/useJobs'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

// ─── Skeleton card — mirrors real card structure to prevent layout shift ──────

function SkeletonCard() {
  return (
    <div
      className="rounded-2xl border border-slate-200 bg-white p-5 flex flex-col gap-3.5 animate-pulse"
      aria-hidden="true"
    >
      {/* Logo + company row */}
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-xl bg-slate-100 flex-shrink-0" />
        <div className="flex-1 space-y-1.5 min-w-0">
          <div className="h-2.5 bg-slate-100 rounded-full w-24" />
          <div className="h-2 bg-slate-100 rounded-full w-16" />
        </div>
      </div>
      {/* Title + location */}
      <div className="space-y-2">
        <div className="h-4 bg-slate-100 rounded-full w-4/5" />
        <div className="h-3 bg-slate-100 rounded-full w-2/5" />
      </div>
      {/* Badges */}
      <div className="flex gap-1.5">
        <div className="h-[22px] bg-slate-100 rounded-full w-16" />
        <div className="h-[22px] bg-slate-100 rounded-full w-14" />
        <div className="h-[22px] bg-slate-100 rounded-full w-20" />
      </div>
      {/* Description lines */}
      <div className="space-y-1.5">
        <div className="h-2.5 bg-slate-100 rounded-full w-full" />
        <div className="h-2.5 bg-slate-100 rounded-full w-5/6" />
      </div>
      {/* Skill tags */}
      <div className="flex gap-1.5">
        <div className="h-[22px] bg-slate-100 rounded-md w-12" />
        <div className="h-[22px] bg-slate-100 rounded-md w-14" />
        <div className="h-[22px] bg-slate-100 rounded-md w-10" />
      </div>
      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-slate-100 mt-auto">
        <div className="h-4 bg-slate-100 rounded-full w-24" />
        <div className="h-7 bg-slate-100 rounded-lg w-16" />
      </div>
    </div>
  )
}

// ─── Empty state ─────────────────────────────────────────────────────────────

function EmptyState({ hasFilters, onReset }) {
  return (
    <div
      className="flex flex-col items-center justify-center py-24 text-center px-4"
      role="status"
      aria-live="polite"
    >
      {/* Illustrated icon */}
      <div className="relative mb-6">
        <div className="w-20 h-20 rounded-full bg-slate-100 flex items-center justify-center">
          {hasFilters
            ? <SearchX size={32} className="text-slate-400" strokeWidth={1.5} />
            : <Briefcase size={32} className="text-slate-400" strokeWidth={1.5} />}
        </div>
        {/* Decorative ring */}
        <div className="absolute inset-0 rounded-full border-2 border-dashed border-slate-200 scale-125 opacity-60" />
      </div>

      <h3 className="text-lg font-bold text-slate-800 mb-2">
        {hasFilters ? 'No matching jobs' : 'No jobs available yet'}
      </h3>
      <p className="text-sm text-slate-500 max-w-[280px] leading-relaxed mb-6">
        {hasFilters
          ? 'Try broadening your search or removing some filters to see more results.'
          : 'Check back soon — new opportunities are posted regularly.'}
      </p>

      {hasFilters && (
        <button
          type="button"
          onClick={onReset}
          className={cn(
            'inline-flex items-center gap-2 px-5 py-2.5 rounded-xl',
            'bg-brand-blue text-white text-sm font-semibold',
            'hover:bg-brand-blue-dark transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2',
          )}
        >
          <X size={14} />
          Reset all filters
        </button>
      )}
    </div>
  )
}


function SearchBar({ value, onSearch }) {
  const [draft, setDraft] = useState(value ?? '')

  const submit = () => onSearch(draft.trim())

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') submit()
  }

  return (
    <div className="mt-8 w-full max-w-2xl">
      <div
        className={cn(
          'flex items-center rounded-2xl border border-border bg-white',
          'shadow-md hover:shadow-lg transition-shadow',
          'focus-within:ring-2 focus-within:ring-brand-blue focus-within:border-brand-blue',
        )}
        role="search"
      >
        <span className="pl-4 pr-2 flex-shrink-0 text-text-muted" aria-hidden="true">
          <Search size={18} />
        </span>

        <input
          type="search"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search job title or keywords"
          aria-label="Search job title or keywords"
          className="flex-1 min-w-0 py-3.5 pr-2 bg-transparent text-sm text-text placeholder:text-text-muted focus:outline-none"
        />

        {draft && (
          <button
            type="button"
            onClick={() => { setDraft(''); onSearch('') }}
            aria-label="Clear search"
            className="p-2 text-text-muted hover:text-text transition-colors flex-shrink-0"
          >
            <X size={15} />
          </button>
        )}

        <button
          type="button"
          onClick={submit}
          aria-label="Search"
          className={cn(
            'flex-shrink-0 m-1.5 px-5 py-2.5 rounded-xl',
            'bg-brand-blue text-white text-sm font-semibold',
            'hover:bg-brand-blue-dark active:scale-95 transition-all',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2',
          )}
        >
          Search
        </button>
      </div>
    </div>
  )
}

// ─── Filter sidebar ───────────────────────────────────────────────────────────

function Divider() {
  return <div className="h-px bg-border my-1" />
}

function FilterSidebar({ filters, salaryRange, onFiltersChange, onSalaryChange, onReset, hasActiveFilters }) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-text">Filters</span>
        {hasActiveFilters && (
          <button
            type="button"
            onClick={onReset}
            className="flex items-center gap-1 text-xs text-brand-blue hover:text-brand-blue-dark transition-colors"
          >
            <X size={11} strokeWidth={2.5} />
            Clear all
          </button>
        )}
      </div>

      <Divider />

      <JobFilters filters={filters} onChange={onFiltersChange} />

      <Divider />

      <div>
        <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
          Work Location
        </p>
        <WorkLocationToggle
          value={filters.work_location ?? null}
          onChange={(val) => onFiltersChange({ ...filters, work_location: val ?? undefined })}
        />
      </div>

      <Divider />

      <div>
        <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
          Salary Range (NGN)
        </p>
        <SalaryRangeSlider
          min={salaryRange.min}
          max={salaryRange.max}
          onChange={onSalaryChange}
        />
      </div>
    </div>
  )
}

// ─── Hero section ─────────────────────────────────────────────────────────────

function HeroSection({ totalJobs, searchQuery, onSearch }) {
  return (
    <div className="bg-white border-b border-border">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14 md:py-20">
        <div className="max-w-2xl">
          <div className="inline-flex items-center gap-2 bg-brand-blue/8 text-brand-blue text-xs font-semibold px-3 py-1.5 rounded-full mb-5">
            <Briefcase size={13} />
            Open Positions
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold text-text leading-tight tracking-tight mb-4">
            Find work that{' '}
            <span className="text-brand-amber">means more</span>
          </h1>

          <p className="text-base sm:text-lg text-text-muted leading-relaxed max-w-xl">
            Discover roles that align with your values, skills, and the change you want to make.
          </p>

          {/* Search bar — directly below hero text */}
          <SearchBar value={searchQuery} onSearch={onSearch} />

          {totalJobs > 0 && (
            <div className="flex flex-wrap items-center gap-5 mt-6">
              <div className="flex items-center gap-2 text-sm text-text-muted">
                <Search size={15} className="text-brand-blue" />
                <span>
                  <strong className="text-text font-semibold">{totalJobs}</strong>{' '}
                  open role{totalJobs !== 1 ? 's' : ''} available
                </span>
              </div>
              <div className="flex items-center gap-2 text-sm text-text-muted">
                <MapPin size={15} className="text-brand-amber" />
                <span>Local &amp; international opportunities</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Listings header ──────────────────────────────────────────────────────────

const SORT_OPTIONS = [
  { value: 'recent', label: 'Most Recent' },
  { value: 'salary_desc', label: 'Highest Salary' },
  { value: 'remote', label: 'Remote First' },
]

function ListingsHeader({ count, loading, sortBy, onSortChange }) {
  return (
    <div className="flex items-center justify-between mb-5">
      <h2 className="text-lg font-bold text-text leading-tight">
        {loading ? 'Loading jobs\u2026' : `All Jobs (${count} job${count !== 1 ? 's' : ''})`}
      </h2>

      <div className="relative flex-shrink-0">
        <label htmlFor="sort-select" className="sr-only">Sort jobs by</label>
        <span
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
          aria-hidden="true"
        >
          <ArrowUpDown size={13} />
        </span>
        <select
          id="sort-select"
          value={sortBy}
          onChange={(e) => onSortChange(e.target.value)}
          className={cn(
            'appearance-none rounded-lg border border-border bg-white',
            'pl-8 pr-8 py-2 text-sm text-text cursor-pointer',
            'focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue',
            'transition-colors hover:border-brand-blue/50',
          )}
        >
          {SORT_OPTIONS.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <ChevronDown
          size={13}
          className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted"
          aria-hidden="true"
        />
      </div>
    </div>
  )
}

// ─── Client-side helpers ──────────────────────────────────────────────────────

function applyClientFilters(jobs, filters) {
  let result = jobs

  if (filters.posted_days) {
    const cutoff = Date.now() - Number(filters.posted_days) * 24 * 60 * 60 * 1000
    result = result.filter((j) => {
      const created = j.created_at ? new Date(j.created_at).getTime() : 0
      return created >= cutoff
    })
  }

  return result
}

function applySort(jobs, sortBy) {
  const copy = [...jobs]
  if (sortBy === 'salary_desc') {
    copy.sort((a, b) => (b.salary_max ?? 0) - (a.salary_max ?? 0))
  } else if (sortBy === 'remote') {
    copy.sort((a, b) => {
      const aR = a.work_model === 'REMOTE' ? 0 : 1
      const bR = b.work_model === 'REMOTE' ? 0 : 1
      return aR - bR
    })
  }
  return copy
}

// ─── Load More button ─────────────────────────────────────────────────────────

function Spinner() {
  return (
    <svg
      className="animate-spin h-4 w-4"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  )
}

function LoadMoreButton({ loading, isRetry, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      aria-label={loading ? 'Loading more jobs' : isRetry ? 'Retry loading jobs' : 'Load more jobs'}
      className={cn(
        'inline-flex items-center gap-2.5 px-8 py-3 rounded-full',
        'border border-slate-200 bg-white text-sm font-semibold text-slate-700',
        'shadow-sm hover:shadow-md hover:border-brand-blue hover:text-brand-blue',
        'transition-all duration-200',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2',
        'disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:shadow-sm disabled:hover:border-slate-200 disabled:hover:text-slate-700',
      )}
    >
      {loading ? (
        <>
          <Spinner />
          <span>Loading more jobs…</span>
        </>
      ) : isRetry ? (
        <>
          <span>↺</span>
          <span>Retry</span>
        </>
      ) : (
        <span>Load more jobs</span>
      )}
    </button>
  )
}

// ─── JobBoardPage ─────────────────────────────────────────────────────────────

const DEFAULT_SALARY = { min: SALARY_MIN, max: SALARY_MAX }

export default function JobBoardPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [filters, setFilters] = useState({})
  const [salaryRange, setSalaryRange] = useState(DEFAULT_SALARY)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sortBy, setSortBy] = useState('recent')

  const apiParams = useMemo(() => ({
    ...(searchQuery ? { q: searchQuery } : {}),
    ...(filters.contract_type ? { contract_type: filters.contract_type } : {}),
    ...(filters.work_model ? { work_model: filters.work_model } : {}),
    ...(filters.work_location ? { work_location: filters.work_location } : {}),
    ...(filters.seniority_level ? { seniority_level: filters.seniority_level } : {}),
    ...(filters.min_years_experience != null ? { min_years_experience: Number(filters.min_years_experience) } : {}),
    ...(filters.max_years_experience != null ? { max_years_experience: Number(filters.max_years_experience) } : {}),
    ...(salaryRange.min > SALARY_MIN ? { salary_min: salaryRange.min } : {}),
    ...(salaryRange.max < SALARY_MAX ? { salary_max: salaryRange.max } : {}),
  }), [searchQuery, filters, salaryRange])

  const { jobs, loading, error, hasMore, loadMore, total } = useJobs({ params: apiParams })
  const { user } = useAuth()

  // Batch has-applied — one request for all visible jobs instead of N individual calls
  const [appliedMap, setAppliedMap] = useState({})
  useEffect(() => {
    if (user?.role !== 'CANDIDATE' || jobs.length === 0) return
    const activeIds = jobs.filter((j) => j.status === 'ACTIVE').map((j) => j.id)
    if (activeIds.length === 0) return

    api.post('/api/v1/applications/has-applied/batch', { job_ids: activeIds })
      .then(({ data }) => setAppliedMap((prev) => ({ ...prev, ...data })))
      .catch(() => {}) // non-critical — individual checks will fall back
  }, [jobs, user?.role])

  const displayedJobs = useMemo(
    () => applySort(applyClientFilters(jobs, filters), sortBy),
    [jobs, filters, sortBy]
  )

  // Track how many jobs were visible before the last load-more so we can
  // animate only the newly appended cards.
  const prevJobCountRef = useRef(0)
  useEffect(() => {
    prevJobCountRef.current = displayedJobs.length
  }, [displayedJobs.length])

  const handleFiltersChange = useCallback((updated) => setFilters(updated), [])
  const handleSalaryChange = useCallback(({ min, max }) => setSalaryRange({ min, max }), [])
  const handleSearch = useCallback((q) => setSearchQuery(q), [])
  const handleReset = useCallback(() => {
    setFilters({})
    setSalaryRange(DEFAULT_SALARY)
    setSearchQuery('')
    setSortBy('recent')
  }, [])

  const hasActiveFilters =
    searchQuery ||
    filters.contract_type ||
    filters.work_model ||
    filters.work_location ||
    filters.seniority_level ||
    filters.posted_days ||
    filters.min_years_experience != null ||
    filters.max_years_experience != null ||
    salaryRange.min > SALARY_MIN ||
    salaryRange.max < SALARY_MAX

  return (
    <>
      <Helmet>
        <title>Browse Jobs in Africa | Elevare</title>
        <meta name="description" content="Find your next role on Elevare — browse hundreds of active job listings across Nigeria and Africa." />
        <meta property="og:title" content="Browse Jobs in Africa | Elevare" />
        <meta property="og:description" content="Find your next role on Elevare — browse hundreds of active job listings across Nigeria and Africa." />
        <meta property="og:url" content="https://elevare.com.ng/jobs" />
        <meta property="og:type" content="website" />
        <link rel="canonical" href="https://elevare.com.ng/jobs" />
      </Helmet>
      <Navbar />

      <div className="pt-16">
        <HeroSection
          totalJobs={total}
          searchQuery={searchQuery}
          onSearch={handleSearch}
        />

        <main className="bg-background min-h-screen">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">

            {/* Mobile filter toggle */}
            <div className="flex items-center justify-between mb-6 lg:hidden">
              <p className="text-sm text-text-muted">
                {loading ? 'Loading\u2026' : `${displayedJobs.length} result${displayedJobs.length !== 1 ? 's' : ''}`}
              </p>
              <button
                type="button"
                className={cn(
                  'flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors',
                  hasActiveFilters
                    ? 'border-brand-blue text-brand-blue bg-brand-blue/5'
                    : 'border-border text-text-muted hover:border-brand-blue hover:text-brand-blue'
                )}
                onClick={() => setSidebarOpen((o) => !o)}
                aria-expanded={sidebarOpen}
                aria-controls="filter-drawer"
              >
                <SlidersHorizontal size={15} />
                Filters
                {hasActiveFilters && (
                  <span className="ml-0.5 w-4 h-4 rounded-full bg-brand-blue text-white text-[10px] font-bold flex items-center justify-center">
                    •
                  </span>
                )}
              </button>
            </div>

            <div className="flex gap-8 items-start">

              {/* Desktop sticky sidebar */}
              <aside
                className="hidden lg:block w-64 flex-shrink-0 sticky top-[88px] self-start max-h-[calc(100vh-104px)] overflow-y-auto"
                aria-label="Job filters"
              >
                <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
                  <FilterSidebar
                    filters={filters}
                    salaryRange={salaryRange}
                    onFiltersChange={handleFiltersChange}
                    onSalaryChange={handleSalaryChange}
                    onReset={handleReset}
                    hasActiveFilters={!!hasActiveFilters}
                  />
                </div>
              </aside>

              {/* Mobile drawer */}
              {sidebarOpen && (
                <>
                  <div
                    className="fixed inset-0 bg-black/40 z-20 lg:hidden"
                    onClick={() => setSidebarOpen(false)}
                    aria-hidden="true"
                  />
                  <div
                    id="filter-drawer"
                    className="fixed inset-y-0 left-0 z-30 w-80 max-w-[85vw] bg-white border-r border-border shadow-xl overflow-y-auto lg:hidden"
                    role="dialog"
                    aria-modal="true"
                    aria-label="Filters"
                  >
                    <div className="flex items-center justify-between px-5 py-4 border-b border-border">
                      <span className="font-semibold text-text">Filters</span>
                      <button
                        type="button"
                        onClick={() => setSidebarOpen(false)}
                        className="p-1.5 rounded-md text-text-muted hover:text-text hover:bg-gray-100 transition-colors"
                        aria-label="Close filters"
                      >
                        <X size={18} />
                      </button>
                    </div>
                    <div className="px-5 py-5">
                      <FilterSidebar
                        filters={filters}
                        salaryRange={salaryRange}
                        onFiltersChange={handleFiltersChange}
                        onSalaryChange={handleSalaryChange}
                        onReset={handleReset}
                        hasActiveFilters={!!hasActiveFilters}
                      />
                    </div>
                  </div>
                </>
              )}

              {/* Main content */}
              <div className="flex-1 min-w-0">

                <ListingsHeader
                  count={total}
                  loading={loading}
                  sortBy={sortBy}
                  onSortChange={setSortBy}
                />

                {error && !loading && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600 mb-6" role="alert">
                    {error}
                  </div>
                )}

                {loading && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
                    {Array.from({ length: 9 }).map((_, i) => (
                      <SkeletonCard key={i} />
                    ))}
                  </div>
                )}

                {!loading && displayedJobs.length === 0 && (
                  <EmptyState
                    hasFilters={!!hasActiveFilters}
                    onReset={handleReset}
                  />
                )}

                {!loading && displayedJobs.length > 0 && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
                    {displayedJobs.map((job, i) => (
                      <div
                        key={job.id}
                        className={cn(
                          i >= prevJobCountRef.current && 'animate-fade-in-up',
                        )}
                        style={
                          i >= prevJobCountRef.current
                            ? { animationDelay: `${(i - prevJobCountRef.current) * 60}ms` }
                            : undefined
                        }
                      >
                        <JobCard job={job} variant="public" initialApplied={appliedMap[job.id] ?? null} />
                      </div>
                    ))}
                  </div>
                )}

                {/* Load more */}
                {hasMore && (
                  <div className="flex justify-center mt-10">
                    <LoadMoreButton
                      loading={loading}
                      isRetry={false}
                      onClick={loadMore}
                    />
                  </div>
                )}

              </div>
            </div>
          </div>
        </main>

        <Footer />
      </div>
    </>
  )
}
