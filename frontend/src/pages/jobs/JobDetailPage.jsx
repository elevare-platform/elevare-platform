import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { trackEvent } from '@/lib/analytics'
import { ArrowLeft, Building2, Calendar, Globe, ExternalLink, Share2, Check } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/context/AuthContext'
import { cn, formatSalary } from '@/lib/utils'
import api from '@/lib/api'
import { ApplyButton } from '@/components/jobs/ApplyButton'

// ─── Badge helpers ────────────────────────────────────────────────────────────

const BADGE_CLASSES = {
  DRAFT:         'bg-gray-100 text-gray-600',
  ACTIVE:        'bg-green-100 text-green-700',
  CLOSED:        'bg-red-100 text-red-600',
  FULL_TIME:     'bg-brand-blue-light text-brand-blue',
  PART_TIME:     'bg-brand-blue-light text-brand-blue',
  CONTRACT:      'bg-purple-100 text-purple-700',
  FREELANCE:     'bg-yellow-100 text-yellow-700',
  INTERNSHIP:    'bg-teal-100 text-teal-700',
  REMOTE:        'bg-green-50 text-green-600',
  HYBRID:        'bg-blue-50 text-blue-600',
  ONSITE:        'bg-orange-50 text-orange-600',
  LOCAL:         'bg-gray-100 text-gray-600',
  INTERNATIONAL: 'bg-indigo-100 text-indigo-700',
}

const LABELS = {
  FULL_TIME:     'Full Time',
  PART_TIME:     'Part Time',
  CONTRACT:      'Contract',
  FREELANCE:     'Freelance',
  INTERNSHIP:    'Internship',
  REMOTE:        'Remote',
  HYBRID:        'Hybrid',
  ONSITE:        'Onsite',
  LOCAL:         'Local',
  INTERNATIONAL: 'International',
  DRAFT:         'Draft',
  ACTIVE:        'Active',
  CLOSED:        'Closed',
}

function Badge({ value }) {
  if (!value) return null
  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        BADGE_CLASSES[value] ?? 'bg-gray-100 text-gray-600'
      )}
    >
      {LABELS[value] ?? value}
    </span>
  )
}

/**
 * Returns true iff the authenticated user is the employer who owns this job.
 */
export function canManageJob(user, job) {
  return (
    user != null &&
    user.role === 'EMPLOYER' &&
    user.id === job.employer_id
  )
}

function SkeletonDetail() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="h-8 bg-gray-200 rounded w-2/3" />
      <div className="flex gap-2">
        <div className="h-5 bg-gray-200 rounded-full w-20" />
        <div className="h-5 bg-gray-200 rounded-full w-16" />
        <div className="h-5 bg-gray-200 rounded-full w-20" />
      </div>
      <div className="h-4 bg-gray-200 rounded w-1/3" />
      <div className="h-4 bg-gray-200 rounded w-1/4" />
      <div className="space-y-2 mt-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-4 bg-gray-200 rounded w-full" />
        ))}
      </div>
    </div>
  )
}

// ─── JobDetailPage ────────────────────────────────────────────────────────────

export default function JobDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()

  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)

  useEffect(() => {
    let cancelled = false

    const fetchJob = async () => {
      setLoading(true)
      setNotFound(false)
      setError(null)
      try {
        const { data } = await api.get(`/api/v1/jobs/${id}`)
        if (!cancelled) {
          setJob(data)
          trackEvent('Jobs', 'view', data.id)
        }
      } catch (err) {
        if (cancelled) return
        if (err.response?.status === 404) setNotFound(true)
        else setError('Something went wrong. Please try again.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchJob()
    return () => { cancelled = true }
  }, [id])

  const handlePublish = async () => {
    setActionError(null)
    setActionLoading(true)
    try {
      const { data } = await api.post(`/api/v1/jobs/${job.id}/publish`)
      setJob((prev) => ({ ...prev, status: data.status ?? 'ACTIVE' }))
    } catch {
      setActionError('Failed to publish job. Please try again.')
    } finally {
      setActionLoading(false)
    }
  }

  const handleClose = async () => {
    setActionError(null)
    setActionLoading(true)
    try {
      const { data } = await api.post(`/api/v1/jobs/${job.id}/close`)
      setJob((prev) => ({ ...prev, status: data.status ?? 'CLOSED' }))
    } catch {
      setActionError('Failed to close job. Please try again.')
    } finally {
      setActionLoading(false)
    }
  }

  const salaryText = (() => {
    const min = job?.salary_min != null ? Number(job.salary_min) : null
    const max = job?.salary_max != null ? Number(job.salary_max) : null
    if (min != null && max != null) return `${formatSalary(min)} – ${formatSalary(max)}`
    if (min != null) return formatSalary(min)
    if (max != null) return formatSalary(max)
    return null
  })()

  const isOwner = job ? canManageJob(user, job) : false
  const [copied, setCopied] = useState(false)

  const handleShare = () => {
    const url = window.location.href
    if (navigator.share) {
      navigator.share({ title: job?.title, url }).catch(() => {})
    } else {
      navigator.clipboard.writeText(url).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      })
    }
  }

  return (
    <>
      <Helmet>
        {job ? (
          <>
            <title>{job.title} — {job.location} | Elevare</title>
            <meta name="description" content={`${job.title} at ${job.company_name || 'a leading company'}. ${job.location} · ${job.contract_type}. Apply on Elevare.`} />
            <meta property="og:title" content={`${job.title} at ${job.company_name || 'Elevare'}`} />
            <meta property="og:description" content={`${job.title} · ${job.location} · ${job.contract_type}. Apply now on Elevare.`} />
            <meta property="og:url" content={`https://elevare.com.ng/jobs/${job.id}`} />
            <meta property="og:type" content="website" />
            <link rel="canonical" href={`https://elevare.com.ng/jobs/${job.id}`} />
          </>
        ) : (
          <title>Job Listing | Elevare</title>
        )}
      </Helmet>
      <Navbar />

      <main className="min-h-screen bg-background">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">

          <div className="flex items-center justify-between mb-6">
            <button
              onClick={() => navigate('/jobs')}
              className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text transition-colors"
              aria-label="Back to job board"
            >
              <ArrowLeft size={16} />
              Back to jobs
            </button>
            {job && (
              <button
                onClick={handleShare}
                className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text transition-colors"
              >
                {copied ? <Check size={15} className="text-green-600" /> : <Share2 size={15} />}
                {copied ? 'Copied!' : 'Share'}
              </button>
            )}
          </div>

          {loading && <SkeletonDetail />}

          {!loading && notFound && (
            <div className="text-center py-20">
              <p className="text-xl font-semibold text-text mb-2">Job not found</p>
              <p className="text-text-muted mb-6">
                This job posting may have been removed or the link is incorrect.
              </p>
              <Link to="/jobs" className="text-brand-blue hover:underline text-sm font-medium">
                Browse all jobs
              </Link>
            </div>
          )}

          {!loading && error && (
            <div className="text-center py-20">
              <p className="text-red-600 mb-4">{error}</p>
              <Button variant="outline" onClick={() => window.location.reload()}>
                Retry
              </Button>
            </div>
          )}

          {!loading && job && (
            <article>
              <div className="flex items-start gap-4 mb-6">
                {job.company_logo_url ? (
                  <img
                    src={job.company_logo_url}
                    alt={`${job.company_name ?? 'Company'} logo`}
                    className="w-14 h-14 rounded-lg object-contain border border-border bg-surface-muted flex-shrink-0"
                  />
                ) : (
                  <span
                    className="w-14 h-14 rounded-lg border border-border bg-surface-muted flex items-center justify-center flex-shrink-0"
                    aria-hidden="true"
                  >
                    <Building2 size={24} className="text-text-muted" />
                  </span>
                )}
                <div className="flex-1 min-w-0">
                  <h1 className="text-2xl font-bold text-text leading-tight mb-1 font-sans">{job.title}</h1>
                  <p className="text-text-muted font-medium">{job.company_name ?? 'Unknown Company'}</p>
                  {job.company_industry && (
                    <p className="text-xs text-text-muted mt-0.5">{job.company_industry}</p>
                  )}
                </div>
              </div>

              <div className="flex flex-wrap gap-2 mb-4">
                <Badge value={job.contract_type} />
                <Badge value={job.work_model} />
                <Badge value={job.work_location} />
                <Badge value={job.status} />
                {job.seniority_level && (
                  <span className={cn('inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium', 'bg-violet-100 text-violet-700')}>
                    {{JUNIOR:'Junior',MID:'Mid-level',SENIOR:'Senior',LEAD:'Lead',EXECUTIVE:'Executive'}[job.seniority_level] ?? job.seniority_level}
                  </span>
                )}
              </div>

              <div className="flex flex-wrap gap-4 text-sm text-text-muted mb-6">
                <span>📍 {job.location}</span>
                {job.required_years_experience != null && (
                  <span>🕐 {job.required_years_experience === 0 ? 'No experience required' : `${job.required_years_experience}+ years experience`}</span>
                )}
                {job.openings_count > 1 && (
                  <span>👥 {job.openings_count} openings</span>
                )}
                {salaryText && <span className="font-semibold text-text">{salaryText}</span>}
                {job.application_deadline && (() => {
                  const date = new Date(job.application_deadline)
                  const daysLeft = Math.ceil((date.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
                  if (daysLeft < 0) return null
                  const label = date.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
                  const urgent = daysLeft <= 3
                  return (
                    <span className={cn(
                      'inline-flex items-center gap-1.5 font-medium',
                      urgent ? 'text-red-600' : 'text-amber-600'
                    )}>
                      <Calendar size={14} />
                      {urgent
                        ? `Applications close in ${daysLeft} day${daysLeft !== 1 ? 's' : ''}`
                        : `Applications close ${label}`}
                    </span>
                  )
                })()}
              </div>

              {isOwner && (
                <div className="flex flex-wrap gap-2 mb-6 p-4 rounded-lg border border-border bg-surface">
                  <span className="text-sm text-text-muted self-center mr-2">Manage:</span>
                  {job.status === 'DRAFT' && (
                    <Button size="sm" onClick={handlePublish} disabled={actionLoading} className="bg-green-600 hover:bg-green-700 text-white border-0">
                      Publish
                    </Button>
                  )}
                  {job.status === 'ACTIVE' && (
                    <Button size="sm" variant="destructive" onClick={handleClose} disabled={actionLoading}>
                      Close
                    </Button>
                  )}
                  {(job.status === 'DRAFT' || job.status === 'ACTIVE') && (
                    <Link to={`/employer/jobs/${job.id}/edit`}>
                      <Button size="sm" variant="outline" disabled={actionLoading}>Edit</Button>
                    </Link>
                  )}
                  {actionError && <p className="w-full text-sm text-red-600 mt-1">{actionError}</p>}
                </div>
              )}

              <div className="prose prose-sm max-w-none text-text">
                <h2 className="text-lg font-semibold text-text mb-3">Job Description</h2>
                <div className="whitespace-pre-wrap text-sm leading-relaxed text-text-muted">
                  {job.description}
                </div>
              </div>

              {/* Required skills */}
              {job.required_skills?.length > 0 && (
                <div className="mt-6">
                  <h2 className="text-base font-semibold text-text mb-3">Required Skills</h2>
                  <div className="flex flex-wrap gap-2">
                    {job.required_skills.map((skill) => (
                      <span
                        key={skill}
                        className="inline-flex items-center px-3 py-1 rounded-full bg-brand-blue/10 text-brand-blue text-xs font-medium"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Company info section */}
              {(job.company_description || job.company_website || job.company_industry) && (
                <div className="mt-8 rounded-xl border border-border bg-surface p-5 space-y-3">
                  <div className="flex items-center gap-3">
                    {job.company_logo_url ? (
                      <img
                        src={job.company_logo_url}
                        alt={`${job.company_name} logo`}
                        className="w-10 h-10 rounded-lg object-contain border border-border bg-background flex-shrink-0"
                      />
                    ) : (
                      <span className="w-10 h-10 rounded-lg border border-border bg-background flex items-center justify-center flex-shrink-0">
                        <Building2 size={18} className="text-text-muted" />
                      </span>
                    )}
                    <div>
                      <p className="font-semibold text-text text-sm">{job.company_name ?? 'About the company'}</p>
                      {job.company_industry && (
                        <p className="text-xs text-text-muted">{job.company_industry}</p>
                      )}
                    </div>
                  </div>

                  {job.company_description && (
                    <p className="text-sm text-text-muted leading-relaxed">{job.company_description}</p>
                  )}

                  {job.company_website && (
                    <a
                      href={job.company_website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-sm text-brand-blue hover:underline"
                    >
                      <Globe size={13} />
                      {job.company_website.replace(/^https?:\/\//, '')}
                      <ExternalLink size={11} />
                    </a>
                  )}
                </div>
              )}

              <div className="mt-8">
                <ApplyButton jobId={job.id} jobStatus={job.status} />
              </div>
            </article>
          )}

        </div>
      </main>

      <Footer />
    </>
  )
}
