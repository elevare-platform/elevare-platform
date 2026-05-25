import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MapPin, ArrowRight, Building2 } from 'lucide-react'
import api from '@/lib/api'

// ─── Company type badge ───────────────────────────────────────────────────────

const BADGE_STYLES = {
  background: '#eff6ff',
  color: '#1d4ed8',
}

function CompanyTypeBadge({ value }) {
  if (!value) return null
  return (
    <span
      style={{
        ...BADGE_STYLES,
        fontSize: '0.6875rem',
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 999,
        whiteSpace: 'nowrap',
      }}
    >
      {value}
    </span>
  )
}

// ─── Skeleton loader ──────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div
      className="animate-pulse rounded-lg border border-border bg-surface p-4"
      aria-hidden="true"
    >
      <div className="h-3 bg-slate-200 rounded w-1/3 mb-3" />
      <div className="h-4 bg-slate-200 rounded w-2/3 mb-2" />
      <div className="h-3 bg-slate-200 rounded w-1/2" />
    </div>
  )
}

// ─── Opportunity card ─────────────────────────────────────────────────────────

/**
 * Renders a single job opportunity card.
 * Requirement 9.2 — role title, company type badge, location, "View Opening →" link.
 */
function OpportunityCard({ job }) {
  // Derive a company type label from available fields
  const companyType = job.industry ?? job.company_type ?? job.work_model ?? null

  return (
    <article className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4 transition-shadow hover:shadow-md">
      {/* Company type badge + location row */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        {companyType ? (
          <CompanyTypeBadge value={companyType} />
        ) : (
          <span className="inline-flex items-center gap-1 text-xs text-text-muted">
            <Building2 size={12} aria-hidden="true" />
            {job.company_name ?? 'Company'}
          </span>
        )}

        {/* Location — Requirement 9.2 */}
        {job.location && (
          <span className="flex items-center gap-1 text-xs text-text-muted">
            <MapPin size={11} aria-hidden="true" />
            {job.location}
          </span>
        )}
      </div>

      {/* Role title — Requirement 9.2 */}
      <h3 className="text-sm font-semibold text-text leading-snug line-clamp-2">
        {job.title}
      </h3>

      {/* "View Opening →" link — Requirement 9.2 */}
      <Link
        to={`/jobs/${job.id}`}
        className="inline-flex items-center gap-1 text-sm font-semibold text-brand-blue hover:text-brand-amber transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue rounded mt-auto"
        aria-label={`View opening for ${job.title}`}
      >
        View Opening <ArrowRight size={13} strokeWidth={2} aria-hidden="true" />
      </Link>
    </article>
  )
}

// ─── OpportunitiesSection ─────────────────────────────────────────────────────

/**
 * Fetches up to 3 active jobs and renders them as opportunity cards.
 *
 * Requirements: 9.1, 9.2, 9.3
 */
export function OpportunitiesSection() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Requirement 9.1 — fetch 3 active jobs on mount, same source as JobBoardPreview
  useEffect(() => {
    let cancelled = false

    api
      .get('/api/v1/jobs', { params: { status: 'active', limit: 3 } })
      .then((res) => {
        if (cancelled) return
        // Handle both { items: [...] } and plain array response shapes
        const data = res.data?.items ?? res.data?.jobs ?? res.data
        setJobs(Array.isArray(data) ? data.slice(0, 3) : [])
      })
      .catch((err) => {
        if (cancelled) return
        setError(err?.response?.data?.detail ?? err.message ?? 'Failed to load opportunities')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [])

  return (
    <section aria-labelledby="opportunities-heading">
      <h2
        id="opportunities-heading"
        className="text-lg font-semibold text-text mb-4"
      >
        Opportunities For You
      </h2>

      {/* Loading skeletons */}
      {loading && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}

      {/* Error state — silent degradation, no jobs shown */}
      {!loading && error && (
        <p className="text-sm text-text-muted py-2">
          Unable to load opportunities right now.
        </p>
      )}

      {/* Job cards — Requirement 9.1, 9.2 */}
      {!loading && !error && jobs.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {jobs.map((job) => (
            <OpportunityCard key={job.id} job={job} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && jobs.length === 0 && (
        <p className="text-sm text-text-muted py-2">
          No open roles at the moment. Check back soon.
        </p>
      )}

      {/* Requirement 9.3 — "Browse All Open Roles →" CTA */}
      <div className="mt-4">
        <Link
          to="/jobs"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand-blue hover:text-brand-amber transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue rounded"
        >
          Browse All Open Roles <ArrowRight size={13} strokeWidth={2} aria-hidden="true" />
        </Link>
      </div>
    </section>
  )
}
