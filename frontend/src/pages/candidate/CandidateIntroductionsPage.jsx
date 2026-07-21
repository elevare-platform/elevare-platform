import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Send, Clock, CheckCircle2, XCircle, Briefcase, Loader2 } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import { useCandidateIntroductions } from '@/hooks/useCandidateIntroductions'

const STATUS_STYLES = {
  PENDING: { icon: Clock, label: 'Awaiting your response', className: 'bg-amber-50 text-amber-700 border-amber-200' },
  ACCEPTED: { icon: CheckCircle2, label: 'Accepted', className: 'bg-green-50 text-green-700 border-green-200' },
  DECLINED: { icon: XCircle, label: 'Declined', className: 'bg-gray-100 text-gray-500 border-gray-200' },
  EXPIRED: { icon: Clock, label: 'Expired', className: 'bg-gray-100 text-gray-500 border-gray-200' },
}

function formatDate(isoString) {
  if (!isoString) return null
  return new Date(isoString).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function IntroductionRow({ intro, onResponded }) {
  const [confirming, setConfirming] = useState(null) // 'accept' | 'decline' | null
  const [submitting, setSubmitting] = useState(false)
  const config = STATUS_STYLES[intro.status] ?? STATUS_STYLES.PENDING
  const Icon = config.icon

  const handleRespond = async (action) => {
    setSubmitting(true)
    try {
      await api.get(`/api/v1/public/introductions/${intro.token}/${action}`)
      onResponded(intro.id, action === 'accept' ? 'ACCEPTED' : 'DECLINED')
    } catch {
      // leave status as-is; user can retry
    } finally {
      setSubmitting(false)
      setConfirming(null)
    }
  }

  return (
    <div className="rounded-xl border border-border bg-white p-4 space-y-3">
      <div className="flex flex-wrap items-center gap-4">
        <span className="w-10 h-10 rounded-full bg-brand-blue/10 flex items-center justify-center flex-shrink-0">
          <Briefcase size={16} className="text-brand-blue" />
        </span>

        <div className="flex-1 min-w-0">
          <p className="font-semibold text-text text-sm truncate">{intro.job_title}</p>
          <p className="text-xs text-text-muted truncate">{intro.employer_name ?? 'An employer'}</p>
        </div>

        <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border flex-shrink-0', config.className)}>
          <Icon size={12} />
          {config.label}
        </span>
      </div>

      <p className="text-xs text-text-muted">
        Requested {formatDate(intro.created_at)}
        {intro.status === 'PENDING' && ` · Expires ${formatDate(intro.expires_at)}`}
        {intro.responded_at && ` · Responded ${formatDate(intro.responded_at)}`}
      </p>

      {intro.status === 'PENDING' && (
        confirming ? (
          <div className="flex items-center gap-2 pt-1">
            <span className="text-xs text-text-muted">
              {confirming === 'accept'
                ? "Accept? The employer will see your profile."
                : 'Decline this introduction?'}
            </span>
            <button
              onClick={() => handleRespond(confirming)}
              disabled={submitting}
              className={cn(
                'text-xs font-semibold px-3 py-1 rounded-lg text-white disabled:opacity-60',
                confirming === 'accept' ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'
              )}
            >
              {submitting ? <Loader2 size={12} className="animate-spin" /> : 'Confirm'}
            </button>
            <button onClick={() => setConfirming(null)} className="text-xs text-text-muted hover:text-text">
              Cancel
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={() => setConfirming('accept')}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-green-600 text-white hover:bg-green-700"
            >
              Accept
            </button>
            <button
              onClick={() => setConfirming('decline')}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-border text-text hover:bg-surface-muted"
            >
              Decline
            </button>
          </div>
        )
      )}
    </div>
  )
}

function SkeletonRow() {
  return (
    <div className="rounded-xl border border-border bg-white p-4 flex items-center gap-4 animate-pulse">
      <div className="w-10 h-10 rounded-full bg-gray-200 flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="h-4 bg-gray-200 rounded w-1/3" />
        <div className="h-3 bg-gray-200 rounded w-1/2" />
      </div>
      <div className="h-6 bg-gray-200 rounded-full w-24" />
    </div>
  )
}

export default function CandidateIntroductionsPage() {
  const { introductions, loading, error, refetch } = useCandidateIntroductions()
  const [items, setItems] = useState(null) // local overlay so status updates instantly

  const list = items ?? introductions

  const handleResponded = (id, status) => {
    setItems(list.map((i) => i.id === id ? { ...i, status } : i))
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-2xl font-bold text-text flex items-center gap-2">
              <Send size={22} className="text-brand-blue" />
              Introduction Requests
            </h1>
            <button onClick={() => { setItems(null); refetch() }} className="text-xs text-brand-blue hover:underline">
              Refresh
            </button>
          </div>
          <p className="text-sm text-text-muted mb-6">
            Employers who'd like to connect with you, in one place — no need to dig through email.
          </p>

          {error && <p className="text-sm text-red-600 mb-4" role="alert">{error}</p>}

          {loading && (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} />)}
            </div>
          )}

          {!loading && !error && list.length === 0 && (
            <div className="text-center py-20">
              <Send size={28} className="mx-auto text-text-muted mb-3" />
              <p className="text-lg font-semibold text-text mb-1">No introduction requests yet</p>
              <p className="text-sm text-text-muted">
                When an employer wants to connect with you, it'll show up here.
                <br />
                <Link to="/candidate/profile" className="text-brand-blue hover:underline">
                  Make sure your profile is visible
                </Link> so employers can find you.
              </p>
            </div>
          )}

          {!loading && list.length > 0 && (
            <div className="space-y-3">
              {list.map((intro) => (
                <IntroductionRow key={intro.id} intro={intro} onResponded={handleResponded} />
              ))}
            </div>
          )}
        </div>
      </main>

      <Footer />
    </div>
  )
}
