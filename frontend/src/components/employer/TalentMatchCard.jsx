import { useState, useEffect } from 'react'
import {
  MapPin, Briefcase, Sparkles, User, Bookmark, BookmarkCheck,
  Send, Coins, Loader2, Clock, CheckCircle2, XCircle, Eye, FileText, Bell,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import CandidateProfilePanel from '@/components/candidates/CandidateProfilePanel'
import SourcedCvModal from '@/components/employer/SourcedCvModal'

function scoreTier(score) {
  if (score == null) return 'grey'
  if (score >= 75) return 'green'
  if (score >= 50) return 'amber'
  return 'grey'
}

const SCORE_STYLES = {
  green: { ring: 'border-green-500', text: 'text-green-700', glow: 'from-green-500/20' },
  amber: { ring: 'border-amber-500', text: 'text-amber-700', glow: 'from-amber-500/20' },
  grey: { ring: 'border-gray-300', text: 'text-gray-500', glow: 'from-gray-400/10' },
}

// 'pending' gets a static badge. 'accepted' gets its own button (view
// profile / download CV) below, not a badge — see the render logic.
// declined/expired deliberately excluded — the credit was refunded, so the
// employer can freely send a fresh request for either of those.
const INTRO_BADGES = {
  pending: { icon: Clock, label: 'Introduction pending', className: 'bg-amber-50 text-amber-700 border-amber-200' },
}

const PAST_ATTEMPT_LABEL = {
  declined: { icon: XCircle, label: 'Previously declined' },
  expired: { icon: Clock, label: 'Previous request expired' },
}

export default function TalentMatchCard({ match, jobId, hasCredits, onCreditSpent, onError }) {
  const tier = scoreTier(match.similarity_score)
  const styles = SCORE_STYLES[tier]
  const displayName = match.candidate_name ?? 'Private profile'

  const [shortlistState, setShortlistState] = useState('idle') // idle | saving | done
  const [introState, setIntroState] = useState('idle') // idle | sending | pending | accepted | declined | expired
  const [showNoCreditsModal, setShowNoCreditsModal] = useState(false)
  const [showShortlistConfirm, setShowShortlistConfirm] = useState(false)
  const [showProfilePanel, setShowProfilePanel] = useState(false)
  const [showCvModal, setShowCvModal] = useState(false)
  const [notifyState, setNotifyState] = useState('idle') // idle | sending | sent

  // 'own_sourced' — an employer's own imported candidate. They already have
  // full access to this profile (Talent Pipeline), so no credit/consent
  // flow is needed — just a free, one-way heads-up that this job might fit.
  // Falls back to the existing Request Introduction flow if `ownership` is
  // absent (older API responses, before this field shipped).
  const isOwnSourced = match.ownership === 'own_sourced'

  // Restore the real introduction status on mount so the badge survives a page reload.
  useEffect(() => {
    if (isOwnSourced) return
    let cancelled = false
    api.get(`/api/v1/jobs/${jobId}/talent-matches/${match.profile_id}/introductions`)
      .then(({ data }) => {
        if (cancelled || !data?.length) return
        const latest = [...data].sort(
          (a, b) => new Date(b.created_at) - new Date(a.created_at)
        )[0]
        setIntroState(latest.status.toLowerCase())
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [jobId, match.profile_id, isOwnSourced])

  // Same idea for own_sourced — restore the 'Notified' state on reload
  // instead of always showing 'Notify for this role'.
  useEffect(() => {
    if (!isOwnSourced) return
    let cancelled = false
    api.get(`/api/v1/jobs/${jobId}/talent-matches/${match.profile_id}/notify`)
      .then(({ data }) => {
        if (cancelled) return
        if (data?.notified) setNotifyState('sent')
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [jobId, match.profile_id, isOwnSourced])

  const handleShortlist = async () => {
    if (shortlistState !== 'idle') return
    setShowShortlistConfirm(false)
    setShortlistState('saving')
    try {
      await api.patch(`/api/v1/talent-pool/${match.profile_id}/status`, { status: 'shortlisted' })
      setShortlistState('done')
    } catch {
      setShortlistState('idle')
      onError?.('Could not shortlist this candidate. Please try again.')
    }
  }

  const handleNotify = async () => {
    if (notifyState !== 'idle') return
    setNotifyState('sending')
    try {
      await api.post(`/api/v1/jobs/${jobId}/talent-matches/${match.profile_id}/notify`)
      setNotifyState('sent')
    } catch {
      setNotifyState('idle')
      onError?.('Could not notify this candidate. Please try again.')
    }
  }

  const handleRequestIntroduction = async () => {
    if (['sending', 'pending', 'accepted'].includes(introState)) return
    setIntroState('sending')
    try {
      await api.post(`/api/v1/jobs/${jobId}/talent-matches/${match.profile_id}/introductions`)
      setIntroState('pending')
      onCreditSpent?.()
    } catch (err) {
      const code = err?.response?.data?.code
      const msg = err?.response?.data?.message ?? ''
      if (code === 'VALIDATION_FAILED' && msg.toLowerCase().includes('already pending')) {
        // Already requested (e.g. duplicate click / stale UI) — reflect the real state
        setIntroState('pending')
      } else {
        setIntroState('idle')
        onError?.('Could not send an introduction request. Please try again.')
      }
    }
  }

  return (
    <div className="group relative rounded-2xl border border-border bg-white p-5 overflow-hidden transition-all hover:shadow-lg hover:-translate-y-0.5">
      {/* Soft gradient accent — stronger for higher-similarity matches */}
      <div
        className={cn(
          'pointer-events-none absolute -top-12 -right-12 w-36 h-36 rounded-full bg-gradient-to-br to-transparent blur-2xl opacity-70 transition-opacity group-hover:opacity-100',
          styles.glow
        )}
        aria-hidden="true"
      />

      <div className="relative flex items-start gap-4">
        <span className="w-11 h-11 rounded-full bg-brand-blue/10 flex items-center justify-center flex-shrink-0">
          <User size={18} className="text-brand-blue" />
        </span>

        <div className="flex-1 min-w-0">
          <p className="font-semibold text-text text-sm truncate">{displayName}</p>
          {(match.current_title || match.profession) && (
            <p className="text-xs text-text-muted truncate mt-0.5">
              {[match.current_title, match.profession].filter(Boolean).join(' · ')}
            </p>
          )}
          <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs text-text-muted">
            {match.location && (
              <span className="flex items-center gap-1">
                <MapPin size={11} />
                {match.location}
              </span>
            )}
            {match.years_of_experience != null && (
              <span className="flex items-center gap-1">
                <Briefcase size={11} />
                {match.years_of_experience} yr{match.years_of_experience !== 1 ? 's' : ''} exp
              </span>
            )}
          </div>
        </div>

        <div
          className={cn(
            'flex items-center justify-center w-14 h-14 rounded-full border-2 flex-shrink-0 bg-white',
            styles.ring
          )}
          title={`${match.similarity_score}% similarity to this job`}
        >
          <span className={cn('text-sm font-bold leading-none', styles.text)}>
            {match.similarity_score}%
          </span>
        </div>
      </div>

      {match.top_skills?.length > 0 && (
        <div className="relative flex flex-wrap gap-1.5 mt-4">
          {match.top_skills.map((skill) => (
            <span
              key={skill}
              className="px-2.5 py-1 rounded-full bg-surface-muted text-text text-[11px] font-medium border border-border"
            >
              {skill}
            </span>
          ))}
        </div>
      )}

      {tier === 'green' && (
        <div className="relative flex items-center gap-1 mt-3 text-[11px] font-semibold text-green-600">
          <Sparkles size={11} />
          Strong match
        </div>
      )}

      {/* Actions */}
      <div className="relative flex items-center gap-2 mt-4 pt-4 border-t border-border">
        <button
          type="button"
          onClick={() => setShowShortlistConfirm(true)}
          disabled={shortlistState !== 'idle'}
          className={cn(
            'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors flex-shrink-0',
            shortlistState === 'done'
              ? 'bg-brand-blue/10 border-brand-blue/30 text-brand-blue'
              : 'border-border text-text-muted hover:text-text hover:bg-surface-muted disabled:opacity-60'
          )}
        >
          {shortlistState === 'saving' ? (
            <Loader2 size={13} className="animate-spin" />
          ) : shortlistState === 'done' ? (
            <BookmarkCheck size={13} />
          ) : (
            <Bookmark size={13} />
          )}
          {shortlistState === 'done' ? 'Shortlisted' : 'Shortlist'}
        </button>

        {showShortlistConfirm && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            onClick={() => setShowShortlistConfirm(false)}
          >
            <div className="absolute inset-0 bg-black/40" aria-hidden="true" />
            <div
              className="relative w-full max-w-sm bg-white rounded-2xl shadow-2xl p-6 space-y-4"
              onClick={(e) => e.stopPropagation()}
              role="dialog"
              aria-modal="true"
              aria-label="Confirm shortlist"
            >
              <div className="flex items-center gap-3">
                <span className="w-10 h-10 rounded-full bg-brand-blue/10 flex items-center justify-center flex-shrink-0">
                  <Bookmark size={18} className="text-brand-blue" />
                </span>
                <div>
                  <p className="font-semibold text-text text-sm">Shortlist {displayName}?</p>
                  <p className="text-xs text-text-muted mt-0.5">This is free and doesn't use a credit.</p>
                </div>
              </div>
              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowShortlistConfirm(false)}
                  className="flex-1 rounded-lg border border-border px-4 py-2 text-sm text-text hover:bg-surface-muted transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleShortlist}
                  className="flex-1 rounded-lg bg-brand-blue text-white px-4 py-2 text-sm font-medium hover:bg-brand-blue/90 transition-colors"
                >
                  Shortlist
                </button>
              </div>
            </div>
          </div>
        )}

        {isOwnSourced ? (
          <button
            type="button"
            onClick={handleNotify}
            disabled={notifyState !== 'idle'}
            className={cn(
              'inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex-1 disabled:opacity-80',
              notifyState === 'sent'
                ? 'bg-green-50 text-green-700 border border-green-200'
                : 'bg-brand-blue text-white hover:bg-brand-blue-dark'
            )}
          >
            {notifyState === 'sending' ? (
              <><Loader2 size={13} className="animate-spin" /> Notifying…</>
            ) : notifyState === 'sent' ? (
              <><CheckCircle2 size={13} /> Notified</>
            ) : (
              <><Bell size={13} /> Notify for this role</>
            )}
          </button>
        ) : introState === 'accepted' ? (
          <button
            type="button"
            onClick={() => match.candidate_profile_id ? setShowProfilePanel(true) : setShowCvModal(true)}
            className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-green-600 text-white hover:bg-green-700 transition-colors flex-1"
          >
            {match.candidate_profile_id ? (
              <><Eye size={13} /> View Full Profile</>
            ) : (
              <><FileText size={13} /> Download CV</>
            )}
          </button>
        ) : INTRO_BADGES[introState] ? (
          <span className={cn(
            'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border flex-1 justify-center',
            INTRO_BADGES[introState].className
          )}>
            {(() => { const Icon = INTRO_BADGES[introState].icon; return <Icon size={13} /> })()}
            {INTRO_BADGES[introState].label}
          </span>
        ) : !hasCredits ? (
          <>
            <button
              type="button"
              onClick={() => setShowNoCreditsModal(true)}
              className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-100 text-amber-700 hover:bg-amber-200 transition-colors flex-1"
            >
              <Coins size={13} />
              Request Introduction
            </button>
            {showNoCreditsModal && (
              <div
                className="fixed inset-0 z-50 flex items-center justify-center p-4"
                onClick={() => setShowNoCreditsModal(false)}
              >
                <div className="absolute inset-0 bg-black/40" aria-hidden="true" />
                <div
                  className="relative w-full max-w-sm bg-white rounded-2xl shadow-2xl p-6 space-y-4"
                  onClick={(e) => e.stopPropagation()}
                  role="dialog"
                  aria-modal="true"
                >
                  <div className="flex items-center gap-3">
                    <span className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
                      <Coins size={18} className="text-amber-600" />
                    </span>
                    <div>
                      <p className="font-semibold text-text text-sm">No credits remaining</p>
                      <p className="text-xs text-text-muted mt-0.5">You need credits to request introductions.</p>
                    </div>
                  </div>
                  <p className="text-sm text-text-muted leading-relaxed">
                    Contact the Elevare team to top up your credit balance. Each introduction request costs 1 credit and is refunded if the candidate declines.
                  </p>
                  <div className="flex gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => setShowNoCreditsModal(false)}
                      className="flex-1 rounded-lg border border-border px-4 py-2 text-sm text-text hover:bg-surface-muted transition-colors"
                    >
                      Close
                    </button>
                    <a
                      href="/contact"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1 rounded-lg bg-brand-blue text-white px-4 py-2 text-sm font-medium text-center hover:bg-brand-blue/90 transition-colors"
                    >
                      Contact us
                    </a>
                  </div>
                </div>
              </div>
            )}
          </>
        ) : (
          <button
            type="button"
            onClick={handleRequestIntroduction}
            disabled={introState === 'sending'}
            className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-blue text-white hover:bg-brand-blue-dark transition-colors disabled:opacity-60 flex-1"
          >
            {introState === 'sending' ? (
              <><Loader2 size={13} className="animate-spin" /> Sending request…</>
            ) : (
              <>
                <Send size={13} />
                Request Introduction
                <span className="inline-flex items-center gap-0.5 bg-white/20 px-1.5 py-0.5 rounded-full text-[10px]">
                  <Coins size={9} /> 1
                </span>
              </>
            )}
          </button>
        )}
      </div>

      {isOwnSourced && notifyState === 'sent' && (
        <p className="relative text-[11px] text-text-muted mt-2 flex items-center gap-1">
          <CheckCircle2 size={11} className="text-green-500 flex-shrink-0" />
          They've been let know about this role — you already have their full profile in your Talent Pipeline.
        </p>
      )}

      {!isOwnSourced && introState === 'pending' && (
        <p className="relative text-[11px] text-text-muted mt-2 flex items-center gap-1">
          <CheckCircle2 size={11} className="text-green-500 flex-shrink-0" />
          We've emailed the candidate. You'll be notified once they respond.
        </p>
      )}

      {PAST_ATTEMPT_LABEL[introState] && (
        <p className="relative text-[11px] text-text-muted mt-2 flex items-center gap-1">
          {(() => { const Icon = PAST_ATTEMPT_LABEL[introState].icon; return <Icon size={11} className="flex-shrink-0" /> })()}
          {PAST_ATTEMPT_LABEL[introState].label} — the credit was refunded, you can request again.
        </p>
      )}

      {showProfilePanel && (
        <CandidateProfilePanel
          profileId={match.candidate_profile_id}
          jobId={jobId}
          onClose={() => setShowProfilePanel(false)}
        />
      )}

      {showCvModal && (
        <SourcedCvModal
          profileId={match.profile_id}
          onClose={() => setShowCvModal(false)}
        />
      )}
    </div>
  )
}
