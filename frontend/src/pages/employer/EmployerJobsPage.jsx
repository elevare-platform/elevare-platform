import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Building2, Globe, Search, X } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { JobCard } from '@/components/jobs/JobCard'
import { useJobs } from '@/hooks/useJobs'
import { Button } from '@/components/ui/button'
import StatusBadge from '@/components/admin/StatusBadge'
import api from '@/lib/api'

// ─── Skeleton placeholder ─────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="rounded-lg border border-border bg-surface p-4 animate-pulse">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded bg-gray-200 flex-shrink-0" />
        <div className="h-3 bg-gray-200 rounded w-24" />
      </div>
      <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
      <div className="h-3 bg-gray-200 rounded w-1/2 mb-3" />
      <div className="flex gap-1.5">
        <div className="h-5 bg-gray-200 rounded-full w-16" />
        <div className="h-5 bg-gray-200 rounded-full w-14" />
      </div>
    </div>
  )
}

// ─── EmployerJobsPage ─────────────────────────────────────────────────────────

/**
 * Employer job management page-  /employer/jobs
 * Protected: EMPLOYER or ADMIN role (enforced via ProtectedRoute in App.jsx)
 * Requirements: 4.1–4.11
 */
const STATUS_FILTERS = [
  { value: 'active',   label: 'Active' },
  { value: 'pending',  label: 'Pending review' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'closed',   label: 'Closed' },
  { value: 'all',      label: 'All' },
]

export default function EmployerJobsPage() {
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('active')

  // Debounce - avoid firing a request on every keystroke
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  const { jobs, setJobs, loading, error, hasMore, loadMore } = useJobs({
    endpoint: '/api/v1/jobs/mine',
    params: { search: debouncedSearch, filter: statusFilter },
  })

  const [profile, setProfile] = useState(null)

  useEffect(() => {
    api.get('/api/v1/employer/profile')
      .then(({ data }) => setProfile(data))
      .catch(() => {})
  }, [])

  const [publishError, setPublishError] = useState(null)

  // Req 4.7-  Publish a DRAFT job and update local state on success
  const handlePublish = useCallback(async (job) => {
    setPublishError(null)
    try {
      await api.post(`/api/v1/jobs/${job.id}/publish`)
      setJobs((prev) =>
        prev.map((j) => (j.id === job.id ? { ...j, status: 'ACTIVE' } : j))
      )
    } catch (err) {
      const body = err.response?.data
      const msg = Array.isArray(body?.details)
        ? body.details.map((e) => e.message).join(', ')
        : body?.message ?? 'Failed to publish. Please try again.'
      setPublishError(msg)
    }
  }, [setJobs])

  // Req 4.8-  Close an ACTIVE job and update local state on success
  const handleClose = useCallback(async (job) => {
    try {
      await api.post(`/api/v1/jobs/${job.id}/close`)
      setJobs((prev) =>
        prev.map((j) => (j.id === job.id ? { ...j, status: 'CLOSED' } : j))
      )
    } catch {
      // Silently ignore - the button remains available for retry
    }
  }, [setJobs])

  const [deleteError, setDeleteError] = useState(null)

  // Delete a draft job and remove it from local state on success
  const handleDelete = useCallback(async (job) => {
    setDeleteError(null)
    try {
      await api.delete(`/api/v1/jobs/${job.id}`)
      setJobs((prev) => prev.filter((j) => j.id !== job.id))
    } catch (err) {
      const body = err.response?.data
      const msg = Array.isArray(body?.details)
        ? body.details.map((e) => e.message).join(', ')
        : body?.message ?? 'Failed to delete. Please try again.'
      setDeleteError(msg)
    }
  }, [setJobs])

  const [resubmitError, setResubmitError] = useState(null)

  // Explicitly resubmit a REJECTED job for another admin review
  const handleResubmit = useCallback(async (job) => {
    setResubmitError(null)
    try {
      await api.post(`/api/v1/jobs/${job.id}/resubmit`)
      setJobs((prev) =>
        prev.map((j) =>
          j.id === job.id ? { ...j, moderation_status: 'PENDING', moderation_reason: null } : j
        )
      )
    } catch (err) {
      const body = err.response?.data
      const msg = Array.isArray(body?.details)
        ? body.details.map((e) => e.message).join(', ')
        : body?.message ?? 'Failed to resubmit. Please try again.'
      setResubmitError(msg)
    }
  }, [setJobs])

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10">

          {/* Company profile banner */}
          {profile && (
            <div className="flex items-center gap-4 mb-8 p-4 rounded-xl border border-border bg-surface">
              {profile.company_logo_url ? (
                <img
                  src={profile.company_logo_url}
                  alt={`${profile.company_name} logo`}
                  className="w-14 h-14 rounded-xl object-contain border border-border bg-background flex-shrink-0"
                />
              ) : (
                <span className="w-14 h-14 rounded-xl border border-border bg-background flex items-center justify-center flex-shrink-0" aria-hidden="true">
                  <Building2 size={24} className="text-text-muted" />
                </span>
              )}
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-text">{profile.company_name}</p>
                <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-0.5 text-xs text-text-muted">
                  {profile.industry && <span>{profile.industry}</span>}
                  {profile.company_size && <span>{profile.company_size} employees</span>}
                  {profile.website && (
                    <a
                      href={profile.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-brand-blue hover:underline"
                    >
                      <Globe size={11} />
                      {profile.website.replace(/^https?:\/\//, '')}
                    </a>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <Link to="/employer/verification" className="flex items-center gap-1.5">
                  <span className="text-xs text-text-muted">Verification:</span>
                  <StatusBadge value={profile.kyc_status ?? 'NOT_SUBMITTED'} />
                </Link>
                <Link to="/employer/onboarding">
                  <Button size="sm" variant="outline">Edit profile</Button>
                </Link>
              </div>
            </div>
          )}

          {/* Page header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-2xl font-bold text-text">My Jobs</h1>
              <p className="text-text-muted text-sm mt-1">
                Manage your job listings
              </p>
            </div>
            <Link to="/employer/jobs/new">
              <Button>Post a job</Button>
            </Link>
          </div>

          {/* Status filter tabs */}
          <div role="tablist" aria-label="Filter jobs by status" className="flex flex-wrap gap-1.5 mb-4">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.value}
                type="button"
                role="tab"
                aria-selected={statusFilter === f.value}
                onClick={() => setStatusFilter(f.value)}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
                  statusFilter === f.value
                    ? 'bg-brand-blue text-white'
                    : 'bg-surface border border-border text-text-muted hover:text-text'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative mb-6 max-w-sm">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" aria-hidden="true" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by job title…"
              aria-label="Search my jobs by title"
              className="w-full pl-9 pr-9 py-2 text-sm rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-brand-blue"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                aria-label="Clear search"
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text"
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Error state */}
          {error && !loading && (
            <p className="text-red-600 text-sm mb-6">{error}</p>
          )}

          {publishError && (
            <div className="mb-4 rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {publishError}
            </div>
          )}

          {deleteError && (
            <div className="mb-4 rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {deleteError}
            </div>
          )}

          {resubmitError && (
            <div className="mb-4 rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {resubmitError}
            </div>
          )}

          {/* Skeleton loading - Req 4.1 */}
          {loading && jobs.length === 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
          )}

          {/* Empty state - Req 4.1 */}
          {!loading && jobs.length === 0 && debouncedSearch && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <p className="text-xl font-semibold text-text mb-2">No jobs match "{debouncedSearch}"</p>
              <p className="text-text-muted mb-6">Try a different title, or clear the search.</p>
              <Button variant="outline" onClick={() => setSearch('')}>Clear search</Button>
            </div>
          )}

          {!loading && jobs.length === 0 && !debouncedSearch && statusFilter === 'active' && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <p className="text-xl font-semibold text-text mb-2">No active jobs</p>
              <p className="text-text-muted mb-6">
                Post your first job to start finding candidates, or check another tab above.
              </p>
              <Link to="/employer/jobs/new">
                <Button>Post a job</Button>
              </Link>
            </div>
          )}

          {!loading && jobs.length === 0 && !debouncedSearch && statusFilter !== 'active' && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <p className="text-xl font-semibold text-text mb-2">
                No {STATUS_FILTERS.find((f) => f.value === statusFilter)?.label.toLowerCase()} jobs
              </p>
              <p className="text-text-muted mb-6">Nothing to show under this filter yet.</p>
              <Button variant="outline" onClick={() => setStatusFilter('active')}>Back to active</Button>
            </div>
          )}

          {/* Job list - Req 4.4–4.10 */}
          {jobs.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {jobs.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  variant="employer"
                  onPublish={handlePublish}
                  onClose={handleClose}
                  onDelete={handleDelete}
                  onResubmit={handleResubmit}
                />
              ))}
            </div>
          )}

          {/* Load more - Req 4.11 */}
          {hasMore && (
            <div className="flex justify-center mt-10">
              <Button
                onClick={loadMore}
                disabled={loading}
                variant="outline"
                className="px-8"
              >
                {loading ? 'Loading…' : 'Load more'}
              </Button>
            </div>
          )}

        </div>
      </main>

      <Footer />
    </div>
  )
}
