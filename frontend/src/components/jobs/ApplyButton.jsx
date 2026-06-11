import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import ApplyModal from '@/components/candidate/ApplyModal'
import api from '@/lib/api'
import { trackEvent } from '@/lib/analytics'

/**
 * ApplyButton — shared apply CTA used on both the job board cards and the
 * job detail page. Fetches has-applied on mount (candidates only) and renders
 * consistently in both contexts.
 *
 * Props:
 *   jobId       — string
 *   jobStatus   — string  (only renders for 'ACTIVE' jobs)
 *   size        — 'sm' | 'default'  (default: 'default')
 *   onApplied   — optional callback fired after a successful application
 */
export function ApplyButton({ jobId, jobStatus, size = 'default', initialApplied = null, onApplied }) {
  const { user } = useAuth()
  const [hasApplied, setHasApplied] = useState(initialApplied)
  const [modalOpen, setModalOpen] = useState(false)
  const [toast, setToast] = useState(false)

  const isCandidate = user?.role === 'CANDIDATE'
  const isActive = jobStatus === 'ACTIVE'

  // Only fire individual check when no batch value was provided
  useEffect(() => {
    if (initialApplied !== null) {
      setHasApplied(initialApplied)
      return
    }
    if (!jobId || !isCandidate || !isActive) return
    let cancelled = false

    api.get(`/api/v1/applications/${jobId}/has-applied`)
      .then(({ data }) => { if (!cancelled) setHasApplied(data.has_applied ?? false) })
      .catch(() => { if (!cancelled) setHasApplied(false) })

    return () => { cancelled = true }
  }, [jobId, isCandidate, isActive, initialApplied])

  if (!isCandidate || !isActive) return null

  const handleSuccess = () => {
    setModalOpen(false)
    setHasApplied(true)
    setToast(true)
    setTimeout(() => setToast(false), 4000)
    trackEvent('Applications', 'apply', jobId)
    onApplied?.()
  }

  if (hasApplied === true) {
    return (
      <span className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-green-100 text-green-700 cursor-default select-none">
        ✓ Already Applied
      </span>
    )
  }

  // Profile incomplete — show nudge instead of apply button
  if (user?.is_profile_complete === false) {
    return (
      <Link
        to="/candidate/profile"
        onClick={(e) => e.stopPropagation()}
        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-amber-100 text-amber-700 hover:bg-amber-200 transition-colors flex-shrink-0"
      >
        Complete profile to apply
      </Link>
    )
  }

  return (
    <>
      <Button
        size={size}
        disabled={hasApplied === null}
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setModalOpen(true) }}
        className="bg-amber-500 hover:bg-amber-600 text-white border-0 disabled:opacity-60 flex-shrink-0"
      >
        {hasApplied === null ? 'Loading…' : 'Apply Now'}
      </Button>

      {modalOpen && (
        <ApplyModal
          jobId={jobId}
          onClose={() => setModalOpen(false)}
          onSuccess={handleSuccess}
        />
      )}

      {toast && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm font-medium text-green-700 shadow-md"
        >
          ✓ Application submitted successfully!
        </div>
      )}
    </>
  )
}
