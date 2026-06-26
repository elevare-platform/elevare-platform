import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Briefcase, Plus, TrendingUp, FileText, CheckCircle, XCircle, FileSearch } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/context/AuthContext'
import { useJobs } from '@/hooks/useJobs'
import { JobCard } from '@/components/jobs/JobCard'
import api from '@/lib/api'

// ─── Stat card ────────────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, colour, loading }) {
  return (
    <div className="bg-white rounded-xl border border-border p-5 flex items-center gap-4">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${colour}`}>
        <Icon size={18} className="text-white" />
      </div>
      <div>
        {loading ? (
          <div className="h-6 w-10 bg-gray-200 rounded animate-pulse mb-1" />
        ) : (
          <p className="text-2xl font-bold text-text">{value ?? 0}</p>
        )}
        <p className="text-xs text-text-muted">{label}</p>
      </div>
    </div>
  )
}

// ─── Skeleton job row ─────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 p-4 border-b border-border animate-pulse">
      <div className="h-4 bg-gray-200 rounded w-1/3" />
      <div className="h-5 bg-gray-200 rounded-full w-16 ml-auto" />
      <div className="h-8 bg-gray-200 rounded w-20" />
    </div>
  )
}

// ─── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const map = {
    ACTIVE:  'bg-green-100 text-green-700',
    DRAFT:   'bg-amber-100 text-amber-700',
    CLOSED:  'bg-gray-100 text-gray-500',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[status] ?? 'bg-gray-100 text-gray-500'}`}>
      {status}
    </span>
  )
}

// ─── EmployerDashboardPage ────────────────────────────────────────────────────

export default function EmployerDashboardPage() {
  const { user } = useAuth()
  const [stats, setStats] = useState(null)
  const [statsLoading, setStatsLoading] = useState(true)
  const [statsError, setStatsError] = useState(null)

  // Recent jobs — first page only, no load-more needed here
  const { jobs, loading: jobsLoading } = useJobs({
    endpoint: '/api/v1/jobs/mine',
    limit: 5,
  })

  // Fetch employer stats
  useEffect(() => {
    const fetchStats = async () => {
      try {
        setStatsLoading(true)
        const { data } = await api.get(`/api/v1/emp/${user.id}/stats`)
        setStats(data)
      } catch (err) {
        // Stats are non-critical — show zeros rather than breaking the page
        setStatsError('Could not load stats')
        setStats({ total_jobs: 0, active_jobs: 0, draft_jobs: 0, closed_jobs: 0, total_applications: 0 })
      } finally {
        setStatsLoading(false)
      }
    }
    fetchStats()
  }, [])

  const isProfileComplete = user?.is_profile_complete

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 space-y-8">

          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-text">
                Welcome back, {user?.first_name}
              </h1>
              <p className="text-text-muted text-sm mt-1">
                {user?.employer_profile?.company_name ?? 'Your employer dashboard'}
              </p>
            </div>
            <Link to="/employer/jobs/new">
              <Button className="flex items-center gap-2">
                <Plus size={16} /> Post a Job
              </Button>
            </Link>
          </div>

          {/* Profile incomplete banner */}
          {!isProfileComplete && (
            <div className="rounded-xl border border-brand-amber/30 bg-brand-amber/5 p-4 flex items-center justify-between gap-4">
              <p className="text-sm text-amber-800">
                Complete your company profile to unlock job posting.
              </p>
              <Link to="/employer/profile">
                <Button size="sm" variant="outline" className="border-brand-amber text-brand-amber hover:bg-brand-amber hover:text-white flex-shrink-0">
                  Complete profile
                </Button>
              </Link>
            </div>
          )}

          {/* Stats cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard
              icon={Briefcase}
              label="Total jobs"
              value={stats?.total_jobs}
              colour="bg-brand-blue"
              loading={statsLoading}
            />
            <StatCard
              icon={CheckCircle}
              label="Active"
              value={stats?.active_jobs}
              colour="bg-green-500"
              loading={statsLoading}
            />
            <StatCard
              icon={FileText}
              label="Drafts"
              value={stats?.draft_jobs}
              colour="bg-brand-amber"
              loading={statsLoading}
            />
            <StatCard
              icon={TrendingUp}
              label="Applications"
              value={stats?.total_applications}
              colour="bg-purple-500"
              loading={statsLoading}
            />
          </div>

          {/* Recent jobs */}
          <div className="bg-white rounded-xl border border-border overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <h2 className="font-semibold text-text text-sm">Recent Jobs</h2>
              <Link to="/employer/jobs" className="text-brand-blue text-xs font-medium hover:underline">
                View all
              </Link>
            </div>

            {/* Loading */}
            {jobsLoading && (
              <>
                <SkeletonRow />
                <SkeletonRow />
                <SkeletonRow />
              </>
            )}

            {/* Empty state */}
            {!jobsLoading && jobs.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-center px-6">
                <Briefcase size={32} className="text-gray-300 mb-3" />
                <p className="font-medium text-text text-sm">No jobs posted yet</p>
                <p className="text-text-muted text-xs mt-1 mb-4">
                  Post your first job to start finding candidates.
                </p>
                <Link to="/employer/jobs/new">
                  <Button size="sm">Post a Job</Button>
                </Link>
              </div>
            )}

            {/* Job rows */}
            {!jobsLoading && jobs.length > 0 && (
              <ul>
                {jobs.map((job) => (
                  <li
                    key={job.id}
                    className="flex items-center gap-3 px-5 py-3 border-b border-border last:border-0 hover:bg-surface-muted transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <Link
                        to={`/jobs/${job.id}`}
                        className="text-sm font-medium text-text hover:text-brand-blue truncate block"
                      >
                        {job.title}
                      </Link>
                      <p className="text-xs text-text-muted truncate">{job.location}</p>
                    </div>
                    <StatusBadge status={job.status} />
                    <Link to={`/employer/jobs/${job.id}/edit`}>
                      <Button size="sm" variant="outline" className="text-xs px-3 py-1 h-auto">
                        Edit
                      </Button>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Quick actions */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Link
              to="/employer/jobs/new"
              className="rounded-xl border border-border bg-white p-5 hover:border-brand-blue/40 hover:shadow-sm transition-all group flex items-center gap-4"
            >
              <div className="w-9 h-9 rounded-lg bg-brand-blue/10 flex items-center justify-center flex-shrink-0">
                <Plus size={18} className="text-brand-blue" />
              </div>
              <div>
                <p className="font-semibold text-text text-sm">Post a New Job</p>
                <p className="text-text-muted text-xs mt-0.5">Create a draft and publish when ready</p>
              </div>
            </Link>
            <Link
              to="/employer/jobs"
              className="rounded-xl border border-border bg-white p-5 hover:border-brand-blue/40 hover:shadow-sm transition-all group flex items-center gap-4"
            >
              <div className="w-9 h-9 rounded-lg bg-brand-blue/10 flex items-center justify-center flex-shrink-0">
                <Briefcase size={18} className="text-brand-blue" />
              </div>
              <div>
                <p className="font-semibold text-text text-sm">Manage Jobs</p>
                <p className="text-text-muted text-xs mt-0.5">View, edit, publish, or close listings</p>
              </div>
            </Link>
            <Link
              to="/employer/cv-parser"
              className="rounded-xl border border-border bg-white p-5 hover:border-brand-blue/40 hover:shadow-sm transition-all group flex items-center gap-4"
            >
              <div className="w-9 h-9 rounded-lg bg-purple-500/10 flex items-center justify-center flex-shrink-0">
                <FileSearch size={18} className="text-purple-500" />
              </div>
              <div>
                <p className="font-semibold text-text text-sm">CV Parser</p>
                <p className="text-text-muted text-xs mt-0.5">Upload CVs and extract candidate data</p>
              </div>
            </Link>
          </div>

        </div>
      </main>

      <Footer />
    </div>
  )
}
