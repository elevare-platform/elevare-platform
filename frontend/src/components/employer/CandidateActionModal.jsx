import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, Loader2, Bell, Send, Coins, CheckCircle2 } from 'lucide-react'
import api from '@/lib/api'
import { useCredits } from '@/hooks/useCredits'

// Sentinel for "not for a specific role" — resolved to a real (hidden,
// standing) job just before submit, via POST /jobs/general-interest. Keeps
// employers with no postings yet from hitting a dead end here.
const GENERAL_INTEREST = '__general_interest__'

/**
 * CandidateActionModal — the real action behind a search result's
 * "Request Introduction" / "Notify" button. Candidate search is
 * deliberately job-less, but the introduction/notify system underneath it
 * (the same one TalentMatchCard uses on the job-matching page) requires a
 * job — so this adds the one missing step: picking which job the action is
 * for, then firing the existing endpoint. No new backend concept.
 *
 * - own_sourced (employer's own uploaded CV): free "Notify" — no credit.
 * - admin_sourced: "Request Introduction" — costs 1 credit, unlocks the CV
 *   only once the candidate accepts.
 */
export default function CandidateActionModal({ match, onClose, onSuccess }) {
  const [jobs, setJobs] = useState([])
  const [jobsLoading, setJobsLoading] = useState(true)
  const [selectedJobId, setSelectedJobId] = useState('')
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState(null)

  const { balance: creditsBalance, loading: creditsLoading } = useCredits()

  const isOwnSourced = match.ownership === 'own_sourced'

  useEffect(() => {
    api.get('/api/v1/jobs/mine', { params: { limit: 100 } })
      .then(({ data }) => {
        const active = (data.items ?? []).filter((j) => j.status === 'ACTIVE')
        setJobs(active)
        // Default to General Interest when there's nothing else to pick —
        // don't leave a new employer with no jobs stuck on a blank select.
        if (active.length === 0) setSelectedJobId(GENERAL_INTEREST)
      })
      .catch(() => setError('Could not load your jobs.'))
      .finally(() => setJobsLoading(false))
  }, [])

  const handleSubmit = async () => {
    if (!selectedJobId || sending) return
    setSending(true)
    setError(null)
    try {
      let jobId = selectedJobId
      if (jobId === GENERAL_INTEREST) {
        const { data } = await api.post('/api/v1/jobs/general-interest')
        jobId = data.id
      }
      if (isOwnSourced) {
        await api.post(`/api/v1/jobs/${jobId}/talent-matches/${match.id}/notify`)
      } else {
        await api.post(`/api/v1/jobs/${jobId}/talent-matches/${match.id}/introductions`)
      }
      setSent(true)
      onSuccess?.()
    } catch (err) {
      const code = err?.response?.data?.code
      const msg = err?.response?.data?.message ?? ''
      if (code === 'VALIDATION_FAILED' && msg.toLowerCase().includes('already pending')) {
        setSent(true)
        onSuccess?.()
      } else {
        setError(msg || 'Something went wrong. Please try again.')
      }
    } finally {
      setSending(false)
    }
  }

  const noCredits = !isOwnSourced && !creditsLoading && (creditsBalance ?? 0) <= 0

  // Portalled to <body> — see SourcedCvModal for why: a fixed-position
  // modal rendered inside a card with a CSS transform/overflow-hidden
  // ancestor gets clipped/repositioned against that card instead of the
  // viewport.
  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="absolute inset-0 bg-black/40" aria-hidden="true" />
      <div className="relative w-full max-w-sm bg-white rounded-2xl shadow-2xl p-6 space-y-4">
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-4 top-4 text-text-muted hover:text-text"
        >
          <X size={18} />
        </button>

        <div>
          <p className="font-semibold text-text text-sm">
            {isOwnSourced ? 'Notify this candidate' : 'Request an introduction'}
          </p>
          <p className="text-xs text-text-muted mt-0.5">{match.current_title || match.candidate_name}</p>
        </div>

        {sent ? (
          <div className="text-center space-y-2 py-4">
            <CheckCircle2 size={28} className="text-green-500 mx-auto" />
            <p className="text-sm text-text font-medium">
              {isOwnSourced ? "They've been notified." : 'Introduction requested.'}
            </p>
            <p className="text-xs text-text-muted">
              {isOwnSourced
                ? 'You already have their full profile in your Talent Pipeline.'
                : "We've emailed the candidate — you'll be notified once they respond."}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-text-muted">Which job is this for?</label>
              {jobsLoading ? (
                <div className="mt-1.5 flex items-center gap-2 text-xs text-text-muted">
                  <Loader2 size={13} className="animate-spin" /> Loading your jobs…
                </div>
              ) : (
                <select
                  value={selectedJobId}
                  onChange={(e) => setSelectedJobId(e.target.value)}
                  className="mt-1.5 w-full rounded-lg border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
                >
                  {jobs.length > 0 && <option value="" disabled>Select a job…</option>}
                  {jobs.map((job) => (
                    <option key={job.id} value={job.id}>{job.title}</option>
                  ))}
                  <option value={GENERAL_INTEREST}>Not for a specific role — General Interest</option>
                </select>
              )}
              {jobs.length === 0 && (
                <p className="mt-1.5 text-xs text-text-muted">
                  You don't have any active job postings yet — that's fine, this will reach out without tying it to a role.
                </p>
              )}
            </div>

            {noCredits && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
                You have no credits remaining. <a href="/contact" target="_blank" rel="noopener noreferrer" className="underline">Contact us</a> to top up.
              </p>
            )}
            {error && (
              <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="button"
              onClick={handleSubmit}
              disabled={!selectedJobId || sending || noCredits}
              className="w-full rounded-lg bg-brand-blue hover:bg-brand-blue-dark disabled:opacity-50 text-white text-sm font-semibold py-2.5 flex items-center justify-center gap-2 transition-colors"
            >
              {sending ? (
                <Loader2 size={15} className="animate-spin" />
              ) : isOwnSourced ? (
                <><Bell size={14} /> Notify Candidate</>
              ) : (
                <><Send size={14} /> Request Introduction <span className="inline-flex items-center gap-0.5 bg-white/20 px-1.5 py-0.5 rounded-full text-[10px]"><Coins size={9} /> 1</span></>
              )}
            </button>
          </div>
        )}
      </div>
    </div>,
    document.body
  )
}
