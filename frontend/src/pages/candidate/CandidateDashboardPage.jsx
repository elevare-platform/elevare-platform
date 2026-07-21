import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  Briefcase, FileText, CheckCircle, TrendingUp,
  ChevronRight, Building2, Star, AlertCircle, Send,
} from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { Button } from '@/components/ui/button'
import { ProfileStrengthBar } from '@/components/candidate/ProfileStrengthBar'
import { useCandidateProfile } from '@/hooks/useCandidateProfile'
import { useCandidateIntroductions } from '@/hooks/useCandidateIntroductions'
import { useAuth } from '@/context/AuthContext'
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

function StatusBadge({ status }) {
  if (!status) return null
  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium', STATUS_BADGE[status] ?? 'bg-gray-100 text-gray-600')}>
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}

// ─── Stat card ────────────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, colour, loading, to, badge }) {
  const content = (
    <div className={cn('flex-1 min-w-[152px] bg-white rounded-xl border border-border p-4 flex flex-col gap-2', to && 'hover:border-brand-blue/40 hover:shadow-md transition-all')}>
      <div className="flex items-center justify-between gap-2">
        <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0', colour)}>
          <Icon size={16} className="text-white" />
        </div>
        {!loading && badge}
      </div>
      {loading ? (
        <div className="h-6 w-10 bg-gray-200 rounded animate-pulse" />
      ) : (
        <p className="text-xl font-bold text-text leading-none">{value ?? 0}</p>
      )}
      <p className="text-xs text-text-muted whitespace-nowrap">{label}</p>
    </div>
  )
  return to ? <Link to={to} className="contents">{content}</Link> : content
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function Skeleton({ className }) {
  return <div className={cn('animate-pulse bg-gray-200 rounded', className)} />
}

// ─── CandidateDashboardPage ───────────────────────────────────────────────────

export default function CandidateDashboardPage() {
  const { user } = useAuth()
  const { profile, loading: profileLoading } = useCandidateProfile()
  const { introductions, loading: introsLoading } = useCandidateIntroductions()
  const pendingIntros = introductions.filter((i) => i.status === 'PENDING').length

  const [applications, setApplications] = useState([])
  const [appsLoading, setAppsLoading] = useState(true)
  const [recentJobs, setRecentJobs] = useState([])
  const [jobsLoading, setJobsLoading] = useState(true)

  // Fetch recent applications (last 5)
  useEffect(() => {
    api.get('/api/v1/applications/me', { params: { limit: 5 } })
      .then(({ data }) => setApplications(data.items ?? data ?? []))
      .catch(() => setApplications([]))
      .finally(() => setAppsLoading(false))
  }, [])

  // Fetch recommended jobs (recent active jobs)
  useEffect(() => {
    api.get('/api/v1/jobs', { params: { limit: 3, status: 'ACTIVE' } })
      .then(({ data }) => setRecentJobs(data.items ?? data ?? []))
      .catch(() => setRecentJobs([]))
      .finally(() => setJobsLoading(false))
  }, [])

  const handleWithdraw = useCallback(async (id) => {
    if (!window.confirm('Withdraw this application?')) return
    try {
      await api.patch(`/api/v1/applications/${id}/withdraw`)
      setApplications((prev) => prev.map((a) => a.id === id ? { ...a, status: 'WITHDRAWN' } : a))
    } catch { /* silently ignore */ }
  }, [])

  // Derive stats from applications
  const stats = {
    total: applications.length,
    reviewing: applications.filter((a) => a.status === 'REVIEWING').length,
    shortlisted: applications.filter((a) => a.status === 'SHORTLISTED').length,
    hired: applications.filter((a) => a.status === 'HIRED').length,
  }

  const defaultCv = profile?.cvs?.find((cv) => cv.is_default) ?? profile?.cvs?.[0]
  const firstName = user?.first_name ?? 'there'

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 space-y-8">

          {/* ── Welcome ── */}
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h1 className="text-2xl font-bold text-text">Welcome back, {firstName}</h1>
              <p className="text-text-muted text-sm mt-0.5">Here's your job search at a glance.</p>
            </div>
            <Link to="/jobs">
              <Button className="flex items-center gap-2">
                <Briefcase size={15} /> Browse Jobs
              </Button>
            </Link>
          </div>

          {/* ── Stats row ── */}
          <div className="flex flex-wrap gap-3">
            <StatCard icon={FileText}    label="Applied"     value={stats.total}       colour="bg-brand-blue"  loading={appsLoading} />
            <StatCard icon={TrendingUp}  label="Reviewing"   value={stats.reviewing}   colour="bg-amber-500"   loading={appsLoading} />
            <StatCard icon={Star}        label="Shortlisted" value={stats.shortlisted} colour="bg-green-500"   loading={appsLoading} />
            <StatCard icon={CheckCircle} label="Hired"       value={stats.hired}       colour="bg-emerald-600" loading={appsLoading} />
            <StatCard
              icon={Send}
              label="Introductions"
              value={introductions.length}
              colour="bg-purple-500"
              loading={introsLoading}
              to="/candidate/introductions"
              badge={pendingIntros > 0 && (
                <span className="px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-semibold whitespace-nowrap">
                  {pendingIntros} new
                </span>
              )}
            />
          </div>

          {/* ── Main grid ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">

            {/* Left col — applications + recommended jobs */}
            <div className="lg:col-span-2 space-y-6">

              {/* Recent Applications */}
              <section className="bg-white rounded-xl border border-border overflow-hidden">
                <div className="flex items-center justify-between px-5 py-4 border-b border-border">
                  <h2 className="font-semibold text-text text-sm">My Applications</h2>
                  <Link to="/candidate/applications" className="text-brand-blue text-xs font-medium hover:underline flex items-center gap-1">
                    View all <ChevronRight size={12} />
                  </Link>
                </div>

                {appsLoading && (
                  <div className="p-4 space-y-3">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="flex items-center gap-3">
                        <Skeleton className="w-10 h-10 rounded-lg flex-shrink-0" />
                        <div className="flex-1 space-y-1.5">
                          <Skeleton className="h-3.5 w-1/2" />
                          <Skeleton className="h-3 w-1/3" />
                        </div>
                        <Skeleton className="h-5 w-16 rounded-full" />
                      </div>
                    ))}
                  </div>
                )}

                {!appsLoading && applications.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-10 text-center px-6">
                    <Briefcase size={28} className="text-gray-300 mb-2" />
                    <p className="text-sm font-medium text-text">No applications yet</p>
                    <p className="text-xs text-text-muted mt-1 mb-4">Start applying to track your progress here.</p>
                    <Link to="/jobs"><Button size="sm">Browse Jobs</Button></Link>
                  </div>
                )}

                {!appsLoading && applications.length > 0 && (
                  <ul>
                    {applications.map((app) => {
                      const canWithdraw = app.status === 'SUBMITTED' || app.status === 'REVIEWING'
                      return (
                        <li key={app.id} className="flex items-center gap-3 px-5 py-3 border-b border-border last:border-0 hover:bg-surface-muted transition-colors">
                          {app.company_logo ? (
                            <img src={app.company_logo} alt="" className="w-9 h-9 rounded-lg object-contain border border-border bg-background flex-shrink-0" />
                          ) : (
                            <span className="w-9 h-9 rounded-lg border border-border bg-background flex items-center justify-center flex-shrink-0">
                              <Building2 size={14} className="text-text-muted" />
                            </span>
                          )}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-text truncate">{app.job_title ?? 'Untitled Job'}</p>
                            <p className="text-xs text-text-muted truncate">{app.company_name ?? 'Unknown Company'}</p>
                          </div>
                          <StatusBadge status={app.status} />
                          {canWithdraw && (
                            <button
                              type="button"
                              onClick={() => handleWithdraw(app.id)}
                              className="text-xs text-red-500 hover:text-red-700 hover:underline flex-shrink-0 focus-visible:outline-none"
                            >
                              Withdraw
                            </button>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                )}
              </section>

              {/* Recommended Jobs */}
              <section className="bg-white rounded-xl border border-border overflow-hidden">
                <div className="flex items-center justify-between px-5 py-4 border-b border-border">
                  <h2 className="font-semibold text-text text-sm">Recommended Jobs</h2>
                  <Link to="/jobs" className="text-brand-blue text-xs font-medium hover:underline flex items-center gap-1">
                    Browse all <ChevronRight size={12} />
                  </Link>
                </div>

                {jobsLoading && (
                  <div className="p-4 space-y-3">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="flex items-center gap-3">
                        <Skeleton className="w-10 h-10 rounded-lg flex-shrink-0" />
                        <div className="flex-1 space-y-1.5">
                          <Skeleton className="h-3.5 w-2/3" />
                          <Skeleton className="h-3 w-1/3" />
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {!jobsLoading && recentJobs.length === 0 && (
                  <p className="text-sm text-text-muted px-5 py-6">No jobs available right now.</p>
                )}

                {!jobsLoading && recentJobs.length > 0 && (
                  <ul>
                    {recentJobs.map((job) => (
                      <li key={job.id} className="flex items-center gap-3 px-5 py-3 border-b border-border last:border-0 hover:bg-surface-muted transition-colors">
                        <span className="w-9 h-9 rounded-lg border border-border bg-background flex items-center justify-center flex-shrink-0">
                          <Building2 size={14} className="text-text-muted" />
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-text truncate">{job.title}</p>
                          <p className="text-xs text-text-muted truncate">{job.company_name ?? job.location}</p>
                        </div>
                        <Link to={`/jobs/${job.id}`} className="text-xs text-brand-blue hover:underline flex-shrink-0">
                          View
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>

            {/* Right col — profile + CV widget */}
            <div className="space-y-5">

              {/* Profile strength */}
              {!profileLoading && profile && (
                <div className="bg-white rounded-xl border border-border p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="font-semibold text-text text-sm">Profile</h2>
                    <Link to="/candidate/profile" className="text-brand-blue text-xs font-medium hover:underline">
                      Edit
                    </Link>
                  </div>
                  <ProfileStrengthBar profile={profile} compact />
                </div>
              )}

              {profileLoading && (
                <div className="bg-white rounded-xl border border-border p-5 space-y-3 animate-pulse">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-2 w-full rounded-full" />
                  <Skeleton className="h-3 w-40" />
                </div>
              )}

              {/* CV widget */}
              <div className="bg-white rounded-xl border border-border p-5">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="font-semibold text-text text-sm">My Documents</h2>
                  <Link to="/candidate/dashboard/documents" className="text-brand-blue text-xs font-medium hover:underline">
                    Manage
                  </Link>
                </div>

                {profileLoading ? (
                  <Skeleton className="h-10 w-full rounded-lg" />
                ) : defaultCv ? (
                  <div className="flex items-center gap-2 rounded-lg border border-border bg-surface-muted px-3 py-2.5">
                    <FileText size={14} className="text-brand-blue flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-text truncate">{defaultCv.filename}</p>
                      <p className="text-[11px] text-text-muted">Default CV</p>
                    </div>
                    {defaultCv.is_default && (
                      <span className="text-[10px] font-semibold text-brand-blue bg-brand-blue/10 px-1.5 py-0.5 rounded-full flex-shrink-0">
                        Default
                      </span>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-3">
                    <p className="text-xs text-text-muted mb-2">No CV uploaded yet</p>
                    <Link to="/candidate/dashboard/documents">
                      <Button size="sm" variant="outline" className="text-xs">Upload CV</Button>
                    </Link>
                  </div>
                )}

                <p className="text-xs text-text-muted mt-2">
                  {profile?.cvs?.length ?? 0} CV{(profile?.cvs?.length ?? 0) !== 1 ? 's' : ''} · {profile?.documents?.length ?? 0} document{(profile?.documents?.length ?? 0) !== 1 ? 's' : ''}
                </p>
              </div>

              {/* Quick links */}
              <div className="bg-white rounded-xl border border-border p-5 space-y-2">
                <h2 className="font-semibold text-text text-sm mb-3">Quick Links</h2>
                {[
                  { label: 'My Applications', to: '/candidate/applications' },
                  { label: 'Introduction Requests', to: '/candidate/introductions' },
                  { label: 'Edit Profile', to: '/candidate/profile' },
                  { label: 'Profile Views', to: '/candidate/profile-views' },
                  { label: 'Browse Jobs', to: '/jobs' },
                ].map(({ label, to }) => (
                  <Link
                    key={to}
                    to={to}
                    className="flex items-center justify-between py-2 text-sm text-text hover:text-brand-blue transition-colors border-b border-border last:border-0"
                  >
                    {label}
                    <ChevronRight size={14} className="text-text-muted" />
                  </Link>
                ))}
              </div>

            </div>
          </div>

        </div>
      </main>

      <Footer />
    </div>
  )
}
