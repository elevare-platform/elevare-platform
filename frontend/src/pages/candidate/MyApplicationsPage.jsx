import { useState, useEffect, useCallback } from 'react'
import { Building2 } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

// ─── Status config ────────────────────────────────────────────────────────────

const STATUS_TABS = ['all', 'SUBMITTED', 'REVIEWING', 'SHORTLISTED', 'HIRED', 'REJECTED', 'WITHDRAWN']

const STATUS_BADGE = {
  SUBMITTED:   'bg-blue-100 text-blue-700',
  REVIEWING:   'bg-amber-100 text-amber-700',
  SHORTLISTED: 'bg-green-100 text-green-700',
  REJECTED:    'bg-red-100 text-red-600',
  HIRED:       'bg-emerald-100 text-emerald-800',
  WITHDRAWN:   'bg-gray-100 text-gray-500',
}

function StatusBadge({ status }) {
  if (!status) return null
  return (
    <span className={cn('inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize', STATUS_BADGE[status] ?? 'bg-gray-100 text-gray-600')}>
      {status}
    </span>
  )
}

function formatAppliedDate(isoString) {
  if (!isoString) return ''
  return `Applied ${new Date(isoString).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}`
}

// ─── Application card ─────────────────────────────────────────────────────────

function ApplicationCard({ application, onWithdraw }) {
  const [withdrawing, setWithdrawing] = useState(false)

  const canWithdraw = application.status === 'SUBMITTED' || application.status === 'REVIEWING'

  const handleWithdraw = async () => {
    if (!window.confirm('Are you sure you want to withdraw this application?')) return
    setWithdrawing(true)
    try {
      await api.patch(`/api/v1/applications/${application.id}/withdraw`)
      onWithdraw(application.id)
    } catch {
      // silently ignore — button stays available for retry
    } finally {
      setWithdrawing(false)
    }
  }

  return (
    <div className="flex items-start gap-4 rounded-lg border border-border bg-surface p-4">
      {/* Logo */}
      {application.company_logo ? (
        <img
          src={application.company_logo}
          alt={`${application.company_name ?? 'Company'} logo`}
          className="w-12 h-12 rounded-lg object-contain border border-border bg-background flex-shrink-0"
        />
      ) : (
        <span className="w-12 h-12 rounded-lg border border-border bg-background flex items-center justify-center flex-shrink-0" aria-hidden="true">
          <Building2 size={20} className="text-text-muted" />
        </span>
      )}

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="font-semibold text-text text-sm leading-snug truncate">
              {application.job_title ?? 'Untitled Job'}
            </p>
            <p className="text-xs text-text-muted mt-0.5">
              {application.company_name ?? 'Unknown Company'}
            </p>
          </div>
          <StatusBadge status={application.status} />
        </div>

        <p className="text-xs text-text-muted mt-2">
          {formatAppliedDate(application.status_updated_at)}
        </p>
      </div>

      {/* Withdraw */}
      {canWithdraw && (
        <Button
          size="sm"
          variant="outline"
          onClick={handleWithdraw}
          disabled={withdrawing}
          className="flex-shrink-0 text-red-600 border-red-200 hover:bg-red-50"
        >
          {withdrawing ? 'Withdrawing…' : 'Withdraw'}
        </Button>
      )}
    </div>
  )
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="flex items-start gap-4 rounded-lg border border-border bg-surface p-4 animate-pulse">
      <div className="w-12 h-12 rounded-lg bg-gray-200 flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="h-4 bg-gray-200 rounded w-1/2" />
        <div className="h-3 bg-gray-200 rounded w-1/3" />
        <div className="h-3 bg-gray-200 rounded w-1/4" />
      </div>
    </div>
  )
}

// ─── MyApplicationsPage ───────────────────────────────────────────────────────

export default function MyApplicationsPage() {
  const [activeTab, setActiveTab] = useState('all')
  const [applications, setApplications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [cursor, setCursor] = useState(null)
  const [hasMore, setHasMore] = useState(false)

  const fetchApplications = useCallback(async (status, nextCursor, replace) => {
    setLoading(true)
    setError(null)
    try {
      const params = { limit: 20 }
      if (status !== 'all') params.status = status
      if (nextCursor) params.cursor = nextCursor

      const { data } = await api.get('/api/v1/applications/me', { params })
      const items = data.items ?? data
      const next = data.next_cursor ?? null

      setApplications((prev) => replace ? items : [...prev, ...items])
      setCursor(next)
      setHasMore(!!next)
    } catch {
      setError('Failed to load applications. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [])

  // Reload when tab changes
  useEffect(() => {
    fetchApplications(activeTab, null, true)
  }, [activeTab, fetchApplications])

  const handleWithdraw = useCallback((id) => {
    setApplications((prev) =>
      prev.map((a) => a.id === id ? { ...a, status: 'WITHDRAWN' } : a)
    )
  }, [])

  return (
    <>
      <Navbar />

      <main className="min-h-screen bg-background">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-10">

          <h1 className="text-2xl font-bold text-text mb-6">My Applications</h1>

          {/* Filter tabs */}
          <div className="flex flex-wrap gap-1.5 mb-6" role="tablist" aria-label="Filter applications">
            {STATUS_TABS.map((tab) => (
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
                {tab}
              </button>
            ))}
          </div>

          {/* Error */}
          {error && (
            <p className="text-sm text-red-600 mb-4" role="alert">{error}</p>
          )}

          {/* Skeleton */}
          {loading && applications.length === 0 && (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          )}

          {/* Empty state */}
          {!loading && applications.length === 0 && !error && (
            <div className="text-center py-20">
              <p className="text-lg font-semibold text-text mb-1">No applications yet</p>
              <p className="text-sm text-text-muted">
                {activeTab === 'all'
                  ? 'Start applying to jobs to track your progress here.'
                  : `No ${activeTab} applications.`}
              </p>
            </div>
          )}

          {/* List */}
          {applications.length > 0 && (
            <div className="space-y-3">
              {applications.map((app) => (
                <ApplicationCard key={app.id} application={app} onWithdraw={handleWithdraw} />
              ))}
            </div>
          )}

          {/* Load more */}
          {hasMore && (
            <div className="flex justify-center mt-8">
              <Button
                variant="outline"
                onClick={() => fetchApplications(activeTab, cursor, false)}
                disabled={loading}
              >
                {loading ? 'Loading…' : 'Load more'}
              </Button>
            </div>
          )}

        </div>
      </main>

      <Footer />
    </>
  )
}
