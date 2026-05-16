import { useCallback } from 'react'
import { Link } from 'react-router-dom'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { JobCard } from '@/components/jobs/JobCard'
import { useJobs } from '@/hooks/useJobs'
import { Button } from '@/components/ui/button'
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
 * Employer job management page — /employer/jobs
 * Protected: EMPLOYER role only (enforced via ProtectedRoute in App.jsx)
 * Requirements: 4.1–4.11
 */
export default function EmployerJobsPage() {
  const { jobs, setJobs, loading, error, hasMore, loadMore } = useJobs({
    endpoint: '/api/v1/jobs/mine',
  })

  // Req 4.7 — Publish a DRAFT job and update local state on success
  const handlePublish = useCallback(async (job) => {
    try {
      await api.post(`/api/v1/jobs/${job.id}/publish`)
      setJobs((prev) =>
        prev.map((j) => (j.id === job.id ? { ...j, status: 'ACTIVE' } : j))
      )
    } catch {
      // Silently ignore — the button remains available for retry
    }
  }, [setJobs])

  // Req 4.8 — Close an ACTIVE job and update local state on success
  const handleClose = useCallback(async (job) => {
    try {
      await api.post(`/api/v1/jobs/${job.id}/close`)
      setJobs((prev) =>
        prev.map((j) => (j.id === job.id ? { ...j, status: 'CLOSED' } : j))
      )
    } catch {
      // Silently ignore — the button remains available for retry
    }
  }, [setJobs])

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10">

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

          {/* Error state */}
          {error && !loading && (
            <p className="text-red-600 text-sm mb-6">{error}</p>
          )}

          {/* Skeleton loading — Req 4.1 */}
          {loading && jobs.length === 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
          )}

          {/* Empty state — Req 4.1 */}
          {!loading && jobs.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <p className="text-xl font-semibold text-text mb-2">No jobs yet</p>
              <p className="text-text-muted mb-6">
                Post your first job to start finding candidates.
              </p>
              <Link to="/employer/jobs/new">
                <Button>Post a job</Button>
              </Link>
            </div>
          )}

          {/* Job list — Req 4.4–4.10 */}
          {jobs.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {jobs.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  variant="employer"
                  onPublish={handlePublish}
                  onClose={handleClose}
                />
              ))}
            </div>
          )}

          {/* Load more — Req 4.11 */}
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
