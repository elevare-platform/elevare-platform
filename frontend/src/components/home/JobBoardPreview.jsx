import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
// api instance from src/lib/api.js — the request interceptor attaches a Bearer
// token only when one is in memory, so this public call goes out without auth.
import api from '@/lib/api'

// ─── Fallback jobs (Requirements 9.4) ────────────────────────────────────────
// Used when the API call fails OR returns an empty array so the section never
// renders empty. Defined at module level so it is stable across renders.

const FALLBACK_JOBS = [
  {
    id: 1,
    title: 'Senior Software Engineer',
    company: 'Flutterwave',
    industry: 'Fintech',
    location: 'Lagos',
    work_mode: 'Hybrid',
    salary_range: '₦800k – ₦1.2M/mo',
  },
  {
    id: 2,
    title: 'Product Manager',
    company: 'Paystack',
    industry: 'Payments',
    location: 'Lagos',
    work_mode: 'Remote',
    salary_range: '₦600k – ₦900k/mo',
  },
  {
    id: 3,
    title: 'Financial Analyst',
    company: 'Access Bank',
    industry: 'Banking',
    location: 'Abuja',
    work_mode: 'On-site',
    salary_range: '₦400k – ₦600k/mo',
  },
  {
    id: 4,
    title: 'UX Designer',
    company: 'Andela',
    industry: 'Tech',
    location: 'Remote',
    work_mode: 'Remote',
    salary_range: '₦500k – ₦750k/mo',
  },
]

// ─── Work-mode badge colours ──────────────────────────────────────────────────

const WORK_MODE_STYLES = {
  REMOTE:  { background: '#f0fdf4', color: '#15803d' },
  HYBRID:  { background: '#fffbeb', color: '#b45309' },
  ONSITE:  { background: '#eff6ff', color: '#1d4ed8' },
}

const WORK_MODE_LABELS = {
  REMOTE: 'Remote',
  HYBRID: 'Hybrid',
  ONSITE: 'On-site',
}

function formatSalary(min, max) {
  if (!min && !max) return null
  const fmt = (n) => `₦${Number(n).toLocaleString('en-NG')}`
  if (min && max) return `${fmt(min)} – ${fmt(max)}`
  if (min) return fmt(min)
  return fmt(max)
}

// ─── JobCard ──────────────────────────────────────────────────────────────────
// Renders a single job listing card (Requirements 9.6).

function JobCard({ job }) {
  const workMode = job.work_model ?? job.work_mode
  const workModeStyle = WORK_MODE_STYLES[workMode] ?? { background: '#f1f5f9', color: '#475569' }
  const workModeLabel = WORK_MODE_LABELS[workMode] ?? workMode
  const salaryDisplay = job.salary_range ?? formatSalary(job.salary_min, job.salary_max)

  return (
    <article
      style={{
        background: '#ffffff',
        borderRadius: '0.75rem',
        border: '1px solid #e2e8f0',
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
        padding: '1.25rem',
        marginBottom: '0.75rem',
        minWidth: 0,
      }}
    >
      {/* Company name + industry badge */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#64748b' }}>
          {job.company_name ?? job.company}
        </span>
        {(job.company_industry ?? job.industry) && (
          <span
            style={{
              fontSize: '0.6875rem',
              fontWeight: 600,
              padding: '2px 8px',
              borderRadius: 999,
              background: '#eff6ff',
              color: '#1d4ed8',
              whiteSpace: 'nowrap',
            }}
          >
            {job.company_industry ?? job.industry}
          </span>
        )}
      </div>

      {/* Job title */}
      <p style={{ margin: '0 0 0.5rem', fontWeight: 700, fontSize: '0.9375rem', color: '#1e293b', lineHeight: 1.3 }}>
        {job.title}
      </p>

      {/* Location + work-mode badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.8125rem', color: '#64748b' }}>📍 {job.location}</span>
        {workMode && (
          <span
            style={{
              fontSize: '0.6875rem',
              fontWeight: 600,
              padding: '2px 8px',
              borderRadius: 999,
              ...workModeStyle,
            }}
          >
            {workModeLabel}
          </span>
        )}
      </div>

      {/* Salary range + Apply Now link */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#1e293b' }}>
          {salaryDisplay ?? ''}
        </span>
        <Link
          to="/jobs"
          style={{
            fontSize: '0.8125rem',
            fontWeight: 600,
            color: '#E87722',
            textDecoration: 'none',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.textDecoration = 'underline' }}
          onMouseLeave={(e) => { e.currentTarget.style.textDecoration = 'none' }}
        >
          Apply Now →
        </Link>
      </div>
    </article>
  )
}

// ─── Skeleton loader (Requirements 9.3) ──────────────────────────────────────

function SkeletonCard() {
  return (
    <div
      className="animate-pulse"
      style={{
        background: '#f1f5f9',
        borderRadius: '0.75rem',
        height: '7rem',
        marginBottom: '0.75rem',
      }}
    />
  )
}

// ─── JobBoardPreview ──────────────────────────────────────────────────────────

export default function JobBoardPreview() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Requirements 9.2 — call the public jobs endpoint on mount.
    // The api instance's request interceptor only attaches Authorization when
    // an access token is in memory; for this public endpoint no token is needed.
    api
      .get('/api/v1/jobs?status=active&limit=8')
      .then((res) => {
        // API returns { items: [...], next_cursor, count, total }
        const data = res.data?.items ?? res.data?.jobs ?? res.data
        const list = Array.isArray(data) && data.length > 0 ? data : null

        // Fallback logic: if the API returns an empty array, use hardcoded jobs
        // so the section never renders empty (Requirements 9.4).
        setJobs(list ?? FALLBACK_JOBS)
      })
      .catch(() => {
        // Fallback logic: on any network or server error, use hardcoded jobs
        // so the section always shows content (Requirements 9.4).
        setJobs(FALLBACK_JOBS)
      })
      .finally(() => setLoading(false))
  }, [])

  return (
    <section
      aria-label="Job board preview"
      style={{
        // Requirements 9.1 — white background
        background: '#ffffff',
        padding: '5rem 1rem',
      }}
    >
      <div
        style={{
          maxWidth: '72rem',
          margin: '0 auto',
        }}
        className="grid grid-cols-1 lg:grid-cols-2 gap-12"
      >
        {/* ── Left column: heading + CTA (Requirements 9.1) ── */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <p
            style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: '#E87722',
              marginBottom: '0.75rem',
            }}
          >
            Live Opportunities
          </p>
          <h2
            style={{
              fontSize: 'clamp(1.75rem, 3vw, 2.5rem)',
              fontWeight: 800,
              color: '#1e293b',
              lineHeight: 1.2,
              marginBottom: '1rem',
            }}
          >
            Roles Open Right Now
          </h2>
          <p
            style={{
              fontSize: '1rem',
              color: '#64748b',
              lineHeight: 1.7,
              marginBottom: '2rem',
              maxWidth: '28rem',
            }}
          >
            Browse live opportunities from Nigeria's top companies. New roles added daily — find your next move today.
          </p>
          <div>
            <Link to="/jobs">
              <Button
                size="lg"
                style={{ background: '#1A4D8F', color: '#ffffff', border: 'none' }}
                className="hover:bg-brand-blue-dark transition-colors"
              >
                Browse All Roles →
              </Button>
            </Link>
          </div>
        </div>

        {/* ── Right column: scrolling job card strip (Requirements 9.5) ── */}
        <div
          style={{
            // Fixed height container that clips the scrolling strip
            height: '28rem',
            overflow: 'hidden',
            // Fade top and bottom edges for a seamless feel
            WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 8%, black 92%, transparent 100%)',
            maskImage: 'linear-gradient(to bottom, transparent 0%, black 8%, black 92%, transparent 100%)',
          }}
        >
          {loading ? (
            // Requirements 9.3 — skeleton loader while fetching
            <div style={{ padding: '0.5rem' }}>
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </div>
          ) : (
            /*
             * Requirements 9.5 — CSS-only continuous upward scroll.
             * The `animate-scroll-y` class (defined in index.css) applies the
             * `scroll-y` keyframe at 20s linear infinite, translating from 0 to
             * -50%. The cards are rendered twice so the second copy fills in
             * exactly as the first copy scrolls out of view (seamless loop).
             * Hovering pauses the animation via the `:hover` rule in index.css.
             */
            <div className="animate-scroll-y" style={{ padding: '0.5rem' }}>
              {/* First copy */}
              {jobs.map((job) => (
                <JobCard key={`a-${job.id}`} job={job} />
              ))}
              {/* Second copy — required for the seamless -50% loop */}
              {jobs.map((job) => (
                <JobCard key={`b-${job.id}`} job={job} />
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
