import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  User, ArrowLeft, ChevronDown, X, MapPin, Briefcase, FileText,
  Star, Info, GraduationCap, Award, Globe, ExternalLink,
  DollarSign, Clock,
} from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

// ─── Status config ────────────────────────────────────────────────────────────

const STATUS_BADGE = {
  SUBMITTED:   'bg-blue-100 text-blue-700',
  REVIEWING:   'bg-amber-100 text-amber-700',
  SHORTLISTED: 'bg-green-100 text-green-700',
  REJECTED:    'bg-red-100 text-red-600',
  HIRED:       'bg-emerald-100 text-emerald-800',
  WITHDRAWN:   'bg-gray-100 text-gray-500',
}

const STATUS_LABELS = {
  SUBMITTED:   'Submitted',
  REVIEWING:   'Reviewing',
  SHORTLISTED: 'Shortlisted',
  REJECTED:    'Rejected',
  HIRED:       'Hired',
  WITHDRAWN:   'Withdrawn',
}

// Valid next statuses per current status (mirrors backend VALID_TRANSITIONS)
const TRANSITIONS = {
  SUBMITTED:   ['REVIEWING', 'REJECTED'],
  REVIEWING:   ['SHORTLISTED', 'REJECTED'],
  SHORTLISTED: ['HIRED', 'REJECTED'],
  HIRED:       [],
  REJECTED:    [],
  WITHDRAWN:   [],
}

const FILTER_TABS = ['all', 'SUBMITTED', 'REVIEWING', 'SHORTLISTED', 'HIRED', 'REJECTED', 'WITHDRAWN']

const SORT_OPTIONS = [
  { value: 'date', label: 'Date Applied' },
  { value: 'score', label: 'Match Score' },
]

function StatusBadge({ status }) {
  if (!status) return null
  return (
    <span className={cn(
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
      STATUS_BADGE[status] ?? 'bg-gray-100 text-gray-600'
    )}>
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}

// ─── Match score badge ────────────────────────────────────────────────────────

function scoreColour(score) {
  if (score === null || score === undefined) return 'bg-gray-100 text-gray-500'
  if (score <= 40) return 'bg-red-100 text-red-600'
  if (score <= 70) return 'bg-amber-100 text-amber-700'
  return 'bg-green-100 text-green-700'
}

function MatchScoreBadge({ score, matchedKeywords = [] }) {
  const [tooltipVisible, setTooltipVisible] = useState(false)
  const hasScore = score !== null && score !== undefined

  const tooltipText = hasScore && matchedKeywords.length > 0
    ? `Matched: ${matchedKeywords.join(', ')}`
    : hasScore
      ? 'No keyword matches found'
      : 'Score not yet computed'

  return (
    <div className="relative inline-flex items-center">
      <button
        type="button"
        onMouseEnter={() => setTooltipVisible(true)}
        onMouseLeave={() => setTooltipVisible(false)}
        onFocus={() => setTooltipVisible(true)}
        onBlur={() => setTooltipVisible(false)}
        aria-label={`Match score: ${hasScore ? `${score}%` : 'not computed'}. ${tooltipText}`}
        className={cn(
          'w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold flex-shrink-0 cursor-default',
          scoreColour(score)
        )}
      >
        {hasScore ? `${score}%` : '—'}
      </button>

      {tooltipVisible && (
        <div
          role="tooltip"
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-10 w-max max-w-xs rounded-lg bg-gray-900 px-3 py-2 text-xs text-white shadow-lg pointer-events-none"
        >
          {tooltipText}
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
        </div>
      )}
    </div>
  )
}

function formatDate(isoString) {
  if (!isoString) return ''
  return new Date(isoString).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

// ─── Candidate profile panel ──────────────────────────────────────────────────

function CandidateProfilePanel({ profileId, jobId, onClose }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [restricted, setRestricted] = useState(false)

  useEffect(() => {
    setLoading(true)
    setRestricted(false)
    const params = jobId ? { job_id: jobId } : {}
    api.get(`/api/v1/candidates/${profileId}`, { params })
      .then(({ data }) => setProfile(data))
      .catch((err) => {
        if (err.response?.status === 403 || err.response?.status === 404) {
          setRestricted(true)
        }
        setProfile(null)
      })
      .finally(() => setLoading(false))
  }, [profileId, jobId])

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" aria-hidden="true" />

      {/* Panel */}
      <div
        className="relative w-full max-w-md bg-white h-full overflow-y-auto shadow-xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Candidate profile"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border sticky top-0 bg-white z-10">
          <h2 className="font-semibold text-text">Candidate Profile</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close panel"
            className="p-1.5 rounded-md text-text-muted hover:text-text hover:bg-surface-muted transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 px-6 py-5">
          {loading && (
            <div className="space-y-4 animate-pulse">
              <div className="flex items-center gap-3">
                <div className="w-14 h-14 rounded-full bg-gray-200" />
                <div className="space-y-2 flex-1">
                  <div className="h-4 bg-gray-200 rounded w-1/2" />
                  <div className="h-3 bg-gray-200 rounded w-1/3" />
                </div>
              </div>
              {[1,2,3].map((i) => <div key={i} className="h-16 bg-gray-200 rounded" />)}
            </div>
          )}

          {!loading && !profile && (
            <p className="text-sm text-text-muted text-center py-10">
              {restricted
                ? 'This candidate has restricted their profile visibility.'
                : 'Profile not available.'}
            </p>
          )}

          {!loading && profile && (
            <div className="space-y-6">
              {/* Identity */}
              <div className="flex items-center gap-4">
                <span className="w-14 h-14 rounded-full bg-brand-blue/10 flex items-center justify-center flex-shrink-0">
                  <User size={24} className="text-brand-blue" />
                </span>
                <div>
                  <p className="font-semibold text-text text-base">
                    {profile.first_name
                      ? `${profile.first_name} ${profile.last_name ?? ''}`.trim()
                      : 'Candidate'}
                  </p>
                  <div className="flex flex-wrap gap-x-3 text-xs text-text-muted mt-0.5">
                    {profile.location && (
                      <span className="flex items-center gap-1"><MapPin size={11} />{profile.location}</span>
                    )}
                    {profile.years_of_experience != null && (
                      <span className="flex items-center gap-1"><Briefcase size={11} />{profile.years_of_experience} yrs exp</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Bio */}
              {profile.bio && (
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-1.5">About</p>
                  <p className="text-sm text-text leading-relaxed">{profile.bio}</p>
                </div>
              )}

              {/* Skills */}
              {profile.skills?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">Skills</p>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.skills.map((s) => (
                      <span key={s} className="px-2.5 py-1 rounded-full bg-brand-blue/10 text-brand-blue text-xs font-medium">{s}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Salary + notice period */}
              {(profile.expected_salary || profile.notice_period_days != null) && (
                <div className="grid grid-cols-2 gap-3">
                  {profile.expected_salary && (
                    <div className="flex items-center gap-2 text-xs text-text-muted">
                      <DollarSign size={13} className="flex-shrink-0" />
                      <span>
                        {profile.expected_currency ?? ''} {Number(profile.expected_salary).toLocaleString()}
                      </span>
                    </div>
                  )}
                  {profile.notice_period_days != null && (
                    <div className="flex items-center gap-2 text-xs text-text-muted">
                      <Clock size={13} className="flex-shrink-0" />
                      <span>{profile.notice_period_days} day notice</span>
                    </div>
                  )}
                </div>
              )}

              {/* Work experience */}
              {profile.work_experiences?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">Work Experience</p>
                  <div className="space-y-3">
                    {profile.work_experiences.map((w) => (
                      <div key={w.id} className="border-l-2 border-brand-blue/30 pl-3">
                        <p className="text-sm font-medium text-text">{w.job_title}</p>
                        <p className="text-xs text-text-muted">{w.company_name}</p>
                        <p className="text-xs text-text-muted">
                          {w.start_date ?? '—'} → {w.is_current ? 'Present' : (w.end_date ?? '—')}
                        </p>
                        {w.description && (
                          <p className="text-xs text-text-muted mt-1 line-clamp-2">{w.description}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Education */}
              {profile.educations?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">Education</p>
                  <div className="space-y-3">
                    {profile.educations.map((e) => (
                      <div key={e.id} className="flex items-start gap-2">
                        <GraduationCap size={14} className="text-text-muted flex-shrink-0 mt-0.5" />
                        <div>
                          <p className="text-sm font-medium text-text">{e.degree} in {e.field_of_study}</p>
                          <p className="text-xs text-text-muted">{e.institution_name}</p>
                          {(e.start_year || e.end_year) && (
                            <p className="text-xs text-text-muted">{e.start_year ?? '—'} – {e.end_year ?? 'Present'}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Certifications */}
              {profile.certifications?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">Certifications</p>
                  <div className="space-y-2">
                    {profile.certifications.map((c) => (
                      <div key={c.id} className="flex items-start gap-2">
                        <Award size={14} className="text-text-muted flex-shrink-0 mt-0.5" />
                        <div>
                          <p className="text-sm font-medium text-text">{c.name}</p>
                          <p className="text-xs text-text-muted">{c.issuing_organization}</p>
                          {c.credential_url && (
                            <a href={c.credential_url} target="_blank" rel="noopener noreferrer"
                              className="text-xs text-brand-blue hover:underline">View credential</a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* CVs */}
              {profile.cvs?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">CVs</p>
                  <ul className="space-y-2">
                    {profile.cvs.map((cv) => (
                      <li key={cv.id} className="flex items-center gap-2 text-sm text-text">
                        <FileText size={14} className="text-brand-blue flex-shrink-0" />
                        <span className="truncate flex-1">{cv.filename}</span>
                        {cv.is_default && (
                          <span className="flex items-center gap-0.5 text-[10px] font-semibold text-brand-blue">
                            <Star size={10} />Default
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Links */}
              {(profile.linkedin_url || profile.github_url || profile.portfolio_url) && (
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">Links</p>
                  <div className="space-y-1.5">
                    {profile.linkedin_url && (
                      <a href={profile.linkedin_url} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-2 text-xs text-brand-blue hover:underline">
                        <ExternalLink size={13} />LinkedIn
                      </a>
                    )}
                    {profile.github_url && (
                      <a href={profile.github_url} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-2 text-xs text-brand-blue hover:underline">
                        <ExternalLink size={13} />GitHub
                      </a>
                    )}
                    {profile.portfolio_url && (
                      <a href={profile.portfolio_url} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-2 text-xs text-brand-blue hover:underline">
                        <Globe size={13} />Portfolio
                      </a>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Applicant card ───────────────────────────────────────────────────────────

function ApplicantCard({ application, jobId, onError }) {
  const [status, setStatus] = useState(application.status)
  const [updating, setUpdating] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)

  const nextStatuses = TRANSITIONS[status] ?? []
  const isTerminal = nextStatuses.length === 0

  const handleStatusChange = async (e) => {
    const newStatus = e.target.value
    if (!newStatus) return
    const prev = status
    setStatus(newStatus) // optimistic update
    setUpdating(true)
    try {
      await api.patch(`/api/v1/applications/${application.id}/status`, { new_status: newStatus })
    } catch {
      setStatus(prev) // revert on failure
      onError('Failed to update status. Please try again.')
    } finally {
      setUpdating(false)
    }
  }

  const handleDownloadCv = async () => {
    try {
      window.open(application.cv_url, '_blank', 'noopener,noreferrer')
    } catch {
      onError('Failed to open CV.')
    }
  }

  // Candidate name — backend needs to add this field; fall back gracefully
  const candidateName = application.candidate_name
    ?? (application.candidate_first_name
      ? `${application.candidate_first_name} ${application.candidate_last_name ?? ''}`.trim()
      : null)
    ?? 'Candidate'

  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">
      {/* Main row */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 p-4">
        {/* Avatar */}
        <span className="w-10 h-10 rounded-full border border-border bg-background flex items-center justify-center flex-shrink-0" aria-hidden="true">
          <User size={16} className="text-text-muted" />
        </span>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-text text-sm">{candidateName}</p>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-0.5 text-xs text-text-muted">
            {application.location && <span>📍 {application.location}</span>}
            {application.years_of_experience != null && (
              <span>{application.years_of_experience} yr{application.years_of_experience !== 1 ? 's' : ''} exp</span>
            )}
            <span>Applied {formatDate(application.status_updated_at)}</span>
          </div>
        </div>

        {/* Status badge */}
        <StatusBadge status={status} />

        {/* Match score badge */}
        <MatchScoreBadge
          score={application.match_score}
          matchedKeywords={application.matched_keywords ?? []}
        />

        {/* Status transition dropdown — only shown for non-terminal statuses */}
        {!isTerminal && (
          <div className="relative flex-shrink-0">
            <select
              defaultValue=""
              disabled={updating}
              onChange={handleStatusChange}
              aria-label="Move application to next status"
              className="appearance-none rounded-md border border-border bg-background pl-3 pr-7 py-1.5 text-xs text-text focus:outline-none focus:ring-2 focus:ring-brand-blue disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              <option value="" disabled>Move to…</option>
              {nextStatuses.map((s) => (
                <option key={s} value={s}>{STATUS_LABELS[s] ?? s}</option>
              ))}
            </select>
            <ChevronDown size={12} className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-text-muted" />
          </div>
        )}

        {/* CV download */}
        {application.cv_url && (
          <Button size="sm" variant="outline" onClick={handleDownloadCv} className="flex-shrink-0">
            Download CV
          </Button>
        )}

        {/* Expand toggle for cover letter */}
        {application.cover_letter && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="flex-shrink-0 text-xs text-brand-blue hover:underline focus-visible:outline-none"
          >
            {expanded ? 'Hide letter' : 'Cover letter'}
          </button>
        )}

        {/* View profile */}
        {application.candidate_profile_id && (
          <button
            type="button"
            onClick={() => setProfileOpen(true)}
            className="flex-shrink-0 text-xs text-brand-blue hover:underline focus-visible:outline-none"
          >
            View profile
          </button>
        )}
      </div>

      {/* Cover letter expansion */}
      {expanded && application.cover_letter && (
        <div className="border-t border-border px-4 py-3 bg-background">
          <p className="text-xs font-medium text-text-muted mb-1">Cover Letter</p>
          <p className="text-sm text-text whitespace-pre-wrap leading-relaxed">
            {application.cover_letter}
          </p>
        </div>
      )}

      {/* Candidate profile panel */}
      {profileOpen && (
        <CandidateProfilePanel
          profileId={application.candidate_profile_id}
          jobId={jobId}
          onClose={() => setProfileOpen(false)}
        />
      )}
    </div>
  )
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="flex items-center gap-4 rounded-lg border border-border bg-surface p-4 animate-pulse">
      <div className="w-10 h-10 rounded-full bg-gray-200 flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="h-4 bg-gray-200 rounded w-1/3" />
        <div className="h-3 bg-gray-200 rounded w-1/2" />
      </div>
      <div className="h-5 bg-gray-200 rounded-full w-20" />
      <div className="h-7 bg-gray-200 rounded w-24" />
    </div>
  )
}

// ─── ApplicantsPage ───────────────────────────────────────────────────────────

export default function ApplicantsPage() {
  const { jobId } = useParams()

  const [jobTitle, setJobTitle] = useState(null)
  const [activeTab, setActiveTab] = useState('all')
  const [applicants, setApplicants] = useState([])
  const [sortBy, setSortBy] = useState('date')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [toast, setToast] = useState(null)
  const [cursor, setCursor] = useState(null)
  const [hasMore, setHasMore] = useState(false)

  const showToast = useCallback((msg) => {
    setToast(msg)
    setTimeout(() => setToast(null), 4000)
  }, [])

  const fetchApplicants = useCallback(async (status, nextCursor, replace) => {
    setLoading(true)
    setError(null)
    try {
      const params = { limit: 20 }
      if (status !== 'all') params.status = status
      if (nextCursor) params.cursor = nextCursor

      const { data } = await api.get(`/api/v1/applications/job/${jobId}`, { params })
      const items = data.items ?? data
      const next = data.next_cursor ?? null

      // Grab job title from first result if available
      if (replace && items.length > 0 && items[0].job_title) {
        setJobTitle(items[0].job_title)
      }

      setApplicants((prev) => replace ? items : [...prev, ...items])
      setCursor(next)
      setHasMore(!!next)
    } catch {
      setError('Failed to load applicants. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [jobId])

  // Fetch job title as fallback when there are no applicants yet
  useEffect(() => {
    if (jobTitle) return
    api.get(`/api/v1/jobs/${jobId}`)
      .then(({ data }) => setJobTitle(data.title))
      .catch(() => {})
  }, [jobId, jobTitle])

  useEffect(() => {
    fetchApplicants(activeTab, null, true)
  }, [activeTab, fetchApplicants])

  const sortedApplicants = [...applicants].sort((a, b) => {
    if (sortBy !== 'score') return 0
    const sa = a.match_score ?? -1
    const sb = b.match_score ?? -1
    return sb - sa
  })

  return (
    <>
      <Navbar />

      <main className="min-h-screen bg-background">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">

          <Link
            to="/employer/jobs"
            className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text mb-6 transition-colors"
          >
            <ArrowLeft size={16} />
            Back to jobs
          </Link>

          <h1 className="text-2xl font-bold text-text mb-6">
            Applicants{jobTitle ? ` for ${jobTitle}` : ''}
          </h1>

          {/* Filter tabs + sort control */}
          <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
            <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Filter applicants by status">
              {FILTER_TABS.map((tab) => (
                <button
                  key={tab}
                  role="tab"
                  aria-selected={activeTab === tab}
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    'px-3 py-1.5 rounded-full text-xs font-medium capitalize transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue',
                    activeTab === tab
                      ? 'bg-brand-blue text-white'
                      : 'bg-surface border border-border text-text-muted hover:text-text'
                  )}
                >
                  {tab === 'all' ? 'All' : STATUS_LABELS[tab]}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <label htmlFor="sort-select" className="text-xs text-text-muted whitespace-nowrap">Sort by:</label>
              <div className="relative">
                <select
                  id="sort-select"
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="appearance-none text-xs rounded-lg border border-border bg-background pl-3 pr-7 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-blue"
                >
                  {SORT_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
                <ChevronDown size={12} className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-text-muted" />
              </div>
            </div>
          </div>

          {error && (
            <p className="text-sm text-red-600 mb-4" role="alert">{error}</p>
          )}

          {loading && applicants.length === 0 && (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          )}

          {!loading && applicants.length === 0 && !error && (
            <div className="text-center py-20">
              <p className="text-lg font-semibold text-text mb-1">No applicants yet</p>
              <p className="text-sm text-text-muted">
                {activeTab === 'all'
                  ? 'Applications will appear here once candidates apply.'
                  : `No ${STATUS_LABELS[activeTab] ?? activeTab} applicants.`}
              </p>
            </div>
          )}

          {applicants.length > 0 && (
            <div className="space-y-3">
              {sortedApplicants.map((app) => (
                <ApplicantCard
                  key={app.id}
                  application={app}
                  jobId={jobId}
                  onError={showToast}
                />
              ))}
            </div>
          )}

          {hasMore && (
            <div className="flex justify-center mt-8">
              <Button
                variant="outline"
                onClick={() => fetchApplicants(activeTab, cursor, false)}
                disabled={loading}
              >
                {loading ? 'Loading…' : 'Load more'}
              </Button>
            </div>
          )}

        </div>
      </main>

      {/* Error toast */}
      {toast && (
        <div
          role="alert"
          aria-live="assertive"
          className="fixed bottom-6 right-6 z-50 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700 shadow-md"
        >
          {toast}
        </div>
      )}

      <Footer />
    </>
  )
}
