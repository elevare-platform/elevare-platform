import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Bell, CheckCircle2 } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { Button } from '@/components/ui/button'
import api from '@/lib/api'
import { useAuth } from '@/context/AuthContext'

/**
 * NotificationDetailPage - the full view of a single notification,
 * reached from the bell dropdown. Fetching it marks it read.
 *
 * The optional actionable link is derived from (type, entity_type) the
 * same way NotificationBell used to hardcode per-item — centralized here
 * instead, since every notification now routes through this page.
 */
function resolveAction(notification) {
  if (notification.type === 'AI_INTERVIEW_INVITE' && notification.entity_type === 'APPLICATION') {
    return {
      label: 'Go to interview',
      to: `/candidate/applications/${notification.entity_id}/interview`,
    }
  }
  if (notification.type === 'NEW_JOB_MATCHES' && notification.entity_type === 'JOB') {
    return { label: 'View matches', to: '/candidate/matches' }
  }
  if (notification.type === 'AI_INTERVIEW_COMPLETED' && notification.entity_type === 'JOB') {
    return {
      label: 'View interview list',
      to: `/employer/jobs/${notification.entity_id}/applicants?tab=interview-list`,
    }
  }
  if (notification.type === 'AI_INTERVIEW_RESET_REQUEST' && notification.entity_type === 'JOB') {
    return {
      label: 'View interview list',
      to: `/employer/jobs/${notification.entity_id}/applicants?tab=interview-list`,
    }
  }
  if (notification.type === 'KYC_SUBMITTED' && notification.entity_type === 'ORGANIZATION') {
    return { label: 'Review submission', to: '/admin/kyc' }
  }
  if (notification.type === 'KYC_APPROVED' && notification.entity_type === 'ORGANIZATION') {
    return { label: 'Post a job', to: '/employer/jobs/new' }
  }
  if (notification.type === 'KYC_REJECTED' && notification.entity_type === 'ORGANIZATION') {
    return { label: 'Resubmit verification', to: '/employer/verification' }
  }
  return null
}

/**
 * Lets an employer resend a candidate's AI interview invite directly from
 * the notification — the whole point of carrying both job_id and
 * talent_pool_profile_id in `context`, instead of just linking to the
 * interview list and making them find the right row themselves.
 */
function ResendInviteAction({ jobId, talentPoolProfileId }) {
  const [state, setState] = useState('idle') // 'idle' | 'sending' | 'sent' | 'error'
  const [errorText, setErrorText] = useState(null)

  const handleResend = async () => {
    setState('sending')
    setErrorText(null)
    try {
      const { data } = await api.post(
        `/api/v1/interviews/${talentPoolProfileId}/send-invite`,
        null,
        { params: { job_id: jobId } }
      )
      if (data.sent) {
        setState('sent')
      } else {
        setErrorText(data.reason || 'Could not resend the invite.')
        setState('error')
      }
    } catch (err) {
      setErrorText(err?.response?.data?.message || 'Could not resend the invite.')
      setState('error')
    }
  }

  if (state === 'sent') {
    return (
      <p className="text-sm text-green-700 flex items-center gap-1.5">
        <CheckCircle2 size={16} />
        Invite resent. The candidate can now try again.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {state === 'error' && <p className="text-sm text-red-700">{errorText}</p>}
      <Button onClick={handleResend} disabled={state === 'sending'}>
        {state === 'sending' ? 'Resending…' : 'Resend interview invite'}
      </Button>
    </div>
  )
}

export default function NotificationDetailPage() {
  const { id } = useParams()
  const { user } = useAuth()
  const [notification, setNotification] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const backTo = user?.role === 'ADMIN' ? '/admin/dashboard' : '/dashboard'

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(false)
    api.get(`/api/v1/notifications/${id}`)
      .then(({ data }) => { if (!cancelled) setNotification(data) })
      .catch(() => { if (!cancelled) setError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [id])

  const action = notification ? resolveAction(notification) : null

  return (
    <>
      <Navbar />

      <main className="min-h-screen bg-background pt-16">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <Link
            to={backTo}
            className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text mb-6 transition-colors"
          >
            <ArrowLeft size={16} />
            Back
          </Link>

          {loading && (
            <div className="space-y-3 animate-pulse">
              <div className="h-6 bg-gray-200 rounded w-2/3" />
              <div className="h-4 bg-gray-200 rounded w-1/3" />
              <div className="h-24 bg-gray-200 rounded" />
            </div>
          )}

          {!loading && (error || !notification) && (
            <div className="text-center py-20">
              <Bell size={28} className="mx-auto text-text-muted mb-3" />
              <p className="text-lg font-semibold text-text mb-1">Notification not found</p>
              <p className="text-sm text-text-muted">
                It may have been removed, or you don't have access to it.
              </p>
            </div>
          )}

          {!loading && !error && notification && (
            <div className="rounded-xl border border-border bg-surface p-6 space-y-4">
              <div>
                <h1 className="text-xl font-bold text-text">{notification.title}</h1>
                <p className="text-xs text-text-muted mt-1">
                  {new Date(notification.created_at).toLocaleDateString(undefined, {
                    month: 'long', day: 'numeric', year: 'numeric',
                  })}
                </p>
              </div>

              {notification.body && (
                <p className="text-sm text-text leading-relaxed whitespace-pre-wrap">
                  {notification.body}
                </p>
              )}

              {notification.type === 'AI_INTERVIEW_RESET_REQUEST'
              && notification.context?.job_id
              && notification.context?.talent_pool_profile_id ? (
                <div className="space-y-3">
                  <ResendInviteAction
                    jobId={notification.context.job_id}
                    talentPoolProfileId={notification.context.talent_pool_profile_id}
                  />
                  {action && (
                    <Link
                      to={action.to}
                      className="inline-block text-sm text-text-muted hover:text-text underline"
                    >
                      {action.label}
                    </Link>
                  )}
                </div>
              ) : (
                action && (
                  <Link
                    to={action.to}
                    className="inline-flex items-center justify-center rounded-lg bg-brand-blue text-white px-4 py-2 text-sm font-medium hover:bg-brand-blue/90 transition-colors"
                  >
                    {action.label}
                  </Link>
                )
              )}
            </div>
          )}
        </div>
      </main>

      <Footer />
    </>
  )
}
