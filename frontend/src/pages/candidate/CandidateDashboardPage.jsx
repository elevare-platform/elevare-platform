import { useRef, useState, useCallback } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { ProfileStrengthBar } from '@/components/candidate/ProfileStrengthBar'
import { CvSection } from '@/components/candidate/CvSection'
import { CvUpload } from '@/components/candidate/CvUpload'
import { DocumentsSection } from '@/components/candidate/DocumentsSection'
import { DocumentUpload } from '@/components/candidate/DocumentUpload'
import { CareerResources } from '@/components/candidate/CareerResources'
import { OpportunitiesSection } from '@/components/candidate/OpportunitiesSection'
import { EmptyState } from '@/components/candidate/EmptyState'
import { useCandidateProfile } from '@/hooks/useCandidateProfile'
import { useAuth } from '@/context/AuthContext'
import { isEmptyState } from '@/lib/candidateUtils'
import api from '@/lib/api'

// ─── Skeleton loader ──────────────────────────────────────────────────────────

function DashboardSkeleton() {
  return (
    <div className="space-y-6 animate-pulse" aria-busy="true" aria-label="Loading profile">
      {/* Strength bar skeleton */}
      <div className="rounded-lg border border-border bg-surface p-5 space-y-3">
        <div className="flex justify-between">
          <div className="h-4 bg-slate-200 rounded w-32" />
          <div className="h-4 bg-slate-200 rounded w-10" />
        </div>
        <div className="h-2 bg-slate-200 rounded-full w-full" />
        <div className="h-3 bg-slate-200 rounded w-64" />
      </div>
      {/* CV section skeleton */}
      <div className="rounded-lg border border-border bg-surface p-5 space-y-3">
        <div className="h-5 bg-slate-200 rounded w-24" />
        <div className="h-14 bg-slate-200 rounded" />
        <div className="h-14 bg-slate-200 rounded" />
      </div>
      {/* Documents section skeleton */}
      <div className="rounded-lg border border-border bg-surface p-5 space-y-3">
        <div className="h-5 bg-slate-200 rounded w-36" />
        <div className="h-14 bg-slate-200 rounded" />
      </div>
    </div>
  )
}

// ─── Inline toast error ───────────────────────────────────────────────────────

function ToastError({ message, onDismiss }) {
  if (!message) return null
  return (
    <div
      role="alert"
      className="flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      <span className="flex items-center gap-2">
        <AlertCircle size={15} aria-hidden="true" />
        {message}
      </span>
      <button
        type="button"
        onClick={onDismiss}
        className="text-red-500 hover:text-red-700 text-xs underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded"
      >
        Dismiss
      </button>
    </div>
  )
}

// ─── CandidateDashboardPage ───────────────────────────────────────────────────

/**
 * Career Hub dashboard page for CANDIDATE users.
 *
 * Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.2, 4.3, 4.4, 5.2, 5.3, 6.5, 7.5, 10.1
 */
export default function CandidateDashboardPage() {
  const { user } = useAuth()
  const { profile, loading, error, refetch, setCvs, setDocuments } = useCandidateProfile()

  // Ref for scrolling to the CV upload zone (Requirement 4.5)
  const cvUploadRef = useRef(null)

  // Inline toast error for action failures (download, delete, set-default)
  const [actionError, setActionError] = useState(null)

  const clearActionError = useCallback(() => setActionError(null), [])

  // ── CV action handlers ──────────────────────────────────────────────────────

  // Requirement 4.2 — download CV via presigned URL
  const handleCvDownload = useCallback(async (id) => {
    try {
      const { data } = await api.get(`/api/v1/candidates/me/cv/${id}/url`)
      window.open(data.url, '_blank', 'noopener,noreferrer')
    } catch (err) {
      setActionError(err?.response?.data?.detail ?? err.message ?? 'Failed to get download URL.')
    }
  }, [])

  // Requirement 4.3 — set default CV with optimistic update
  const handleCvSetDefault = useCallback(async (id) => {
    // Optimistic update
    setCvs((prev) => prev.map((cv) => ({ ...cv, is_default: cv.id === id })))
    try {
      await api.put(`/api/v1/candidates/me/cv/${id}/default`)
    } catch (err) {
      // Revert on failure by refetching
      refetch()
      setActionError(err?.response?.data?.detail ?? err.message ?? 'Failed to set default CV.')
    }
  }, [setCvs, refetch])

  // Requirement 4.4 — delete CV with optimistic update
  const handleCvDelete = useCallback(async (id) => {
    // Optimistic update
    setCvs((prev) => prev.filter((cv) => cv.id !== id))
    try {
      await api.delete(`/api/v1/candidates/me/cv/${id}`)
    } catch (err) {
      // Revert on failure by refetching
      refetch()
      setActionError(err?.response?.data?.detail ?? err.message ?? 'Failed to delete CV.')
    }
  }, [setCvs, refetch])

  // Requirement 6.5 — optimistic append after CV upload
  const handleCvUploadSuccess = useCallback((newCv) => {
    setCvs((prev) => [...prev, newCv])
  }, [setCvs])

  // ── Document action handlers ────────────────────────────────────────────────

  // Requirement 5.2 — download document via presigned URL
  const handleDocDownload = useCallback(async (id) => {
    try {
      const { data } = await api.get(`/api/v1/candidates/me/documents/${id}/url`)
      window.open(data.url, '_blank', 'noopener,noreferrer')
    } catch (err) {
      setActionError(err?.response?.data?.detail ?? err.message ?? 'Failed to get download URL.')
    }
  }, [])

  // Requirement 5.3 — delete document with optimistic update
  const handleDocDelete = useCallback(async (id) => {
    // Optimistic update
    setDocuments((prev) => prev.filter((doc) => doc.id !== id))
    try {
      await api.delete(`/api/v1/candidates/me/documents/${id}`)
    } catch (err) {
      // Revert on failure by refetching
      refetch()
      setActionError(err?.response?.data?.detail ?? err.message ?? 'Failed to delete document.')
    }
  }, [setDocuments, refetch])

  // Requirement 7.5 — optimistic append after document upload
  const handleDocUploadSuccess = useCallback((newDoc) => {
    setDocuments((prev) => [...prev, newDoc])
  }, [setDocuments])

  // ── Render ──────────────────────────────────────────────────────────────────

  const firstName = user?.first_name ?? 'there'
  const empty = isEmptyState(profile)

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-10 space-y-8">

          {/* Requirement 2.3 — page heading + personalised greeting */}
          <div>
            <h1 className="text-2xl font-bold text-text">Your Career Hub</h1>
            <p className="text-text-muted text-sm mt-1">
              Welcome back, {firstName}.
            </p>
          </div>

          {/* Requirement 2.2 — skeleton while loading */}
          {loading && <DashboardSkeleton />}

          {/* Requirement 2.4 — inline error + retry on failure */}
          {!loading && error && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-6 flex flex-col items-center gap-4 text-center">
              <AlertCircle size={32} className="text-red-400" aria-hidden="true" />
              <div>
                <p className="font-semibold text-red-700">Failed to load your profile</p>
                <p className="text-sm text-red-600 mt-1">{error}</p>
              </div>
              <button
                type="button"
                onClick={refetch}
                className="inline-flex items-center gap-2 rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
              >
                <RefreshCw size={14} aria-hidden="true" />
                Retry
              </button>
            </div>
          )}

          {/* Action error toast */}
          {actionError && (
            <ToastError message={actionError} onDismiss={clearActionError} />
          )}

          {/* Requirement 10.1 — conditionally render empty state vs full dashboard */}
          {!loading && !error && profile && (
            <>
              {empty ? (
                /* Empty state — Requirement 10.1 through 10.6 */
                <EmptyState firstName={firstName} profile={profile} />
              ) : (
                /* Full dashboard */
                <div className="space-y-8">
                  {/* Profile Strength — Requirements 3.1–3.5 */}
                  <ProfileStrengthBar profile={profile} />

                  {/* CVs + Upload — Requirements 4.x, 6.x */}
                  <section className="space-y-4">
                    <CvSection
                      cvs={profile.cvs ?? []}
                      onDownload={handleCvDownload}
                      onSetDefault={handleCvSetDefault}
                      onDelete={handleCvDelete}
                      uploadRef={cvUploadRef}
                    />
                    <div ref={cvUploadRef}>
                      <CvUpload onUploadSuccess={handleCvUploadSuccess} />
                    </div>
                  </section>

                  {/* Documents + Upload — Requirements 5.x, 7.x */}
                  <section className="space-y-4">
                    <DocumentsSection
                      documents={profile.documents ?? []}
                      onDownload={handleDocDownload}
                      onDelete={handleDocDelete}
                    />
                    <DocumentUpload onUploadSuccess={handleDocUploadSuccess} />
                  </section>

                  {/* Career Resources — Requirements 8.x */}
                  <CareerResources />

                  {/* Opportunities — Requirements 9.x */}
                  <OpportunitiesSection />
                </div>
              )}
            </>
          )}

        </div>
      </main>

      <Footer />
    </div>
  )
}
