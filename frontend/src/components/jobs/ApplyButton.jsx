import { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import ApplyModal from '@/components/candidate/ApplyModal'
import api from '@/lib/api'
import { trackEvent } from '@/lib/analytics'

export function ApplyButton({ jobId, jobStatus, size = 'default', initialApplied = null, onApplied }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [hasApplied, setHasApplied] = useState(initialApplied)
  const [modalOpen, setModalOpen] = useState(false)
  const [toast, setToast] = useState(false)

  const isCandidate = user?.role === 'CANDIDATE'
  const isActive = jobStatus === 'ACTIVE'

  useEffect(() => {
    if (initialApplied !== null) { setHasApplied(initialApplied); return }
    if (!jobId || !isCandidate || !isActive) return
    let cancelled = false
    api.get(`/api/v1/applications/${jobId}/has-applied`)
      .then(({ data }) => { if (!cancelled) setHasApplied(data.has_applied ?? false) })
      .catch(() => { if (!cancelled) setHasApplied(false) })
    return () => { cancelled = true }
  }, [jobId, isCandidate, isActive, initialApplied])

  // Not active — never show the button
  if (!isActive) return null

  // Unauthenticated — show Apply Now, redirect to login with return URL
  if (!user) {
    return (
      <Button
        size={size}
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          navigate(`/login?next=${encodeURIComponent(location.pathname)}`)
        }}
        className="bg-amber-500 hover:bg-amber-600 text-white border-0 flex-shrink-0"
      >
        Apply Now
      </Button>
    )
  }

  // Unverified — nudge to verify before applying
  if (user.account_status === 'PENDING_VERIFICATION') {
    return (
      <div className="flex flex-col gap-1.5" onClick={(e) => e.stopPropagation()}>
        <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          Verify your email to apply.
        </span>
        <button
          type="button"
          onClick={() => api.post('/api/v1/auth/resend-verification-email').catch(() => {})}
          className="text-xs text-brand-blue hover:underline text-left"
        >
          Resend verification email →
        </button>
      </div>
    )
  }

  // Employer / admin — don't show apply button
  if (!isCandidate) return null

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

  if (user?.is_profile_complete === false) {
    return (
      <Link
        to={`/candidate/profile?next=${encodeURIComponent(location.pathname)}`}
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
