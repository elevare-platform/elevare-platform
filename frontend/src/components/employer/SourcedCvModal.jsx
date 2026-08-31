import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X, Users, Brain, Download } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import { matchScoreBand } from '@/lib/matchScore'

/**
 * SourcedCvModal - shown for sourced-only talent pool profiles (no
 * CandidateProfile, no login) once an introduction has been ACCEPTED.
 * There's no separate "profile" to view for these - the parsed CV data
 * itself, fetched by profile ID, is the full extent of what's available.
 */
export default function SourcedCvModal({ profileId, jobId, hasInterviewBrief, onClose, onSent }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const [emailInput, setEmailInput] = useState('')
  const [savingEmail, setSavingEmail] = useState(false)
  const [emailResult, setEmailResult] = useState(null) // { ok: bool, message: string } | null

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(false)
    const params = jobId ? { job_id: jobId } : {}
    api.get(`/api/v1/talent-pool/${profileId}`, { params })
      .then(({ data }) => { if (!cancelled) setProfile(data) })
      .catch(() => { if (!cancelled) setError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [profileId, jobId])

  const handleSaveEmail = async () => {
    if (!emailInput.trim() || savingEmail) return
    setSavingEmail(true)
    setEmailResult(null)
    try {
      const { data } = await api.patch(`/api/v1/talent-pool/${profileId}/email`, {
        email: emailInput.trim(),
      })
      setProfile(data)

      if (jobId && hasInterviewBrief) {
        try {
          const { data: sendData } = await api.post(
            `/api/v1/interviews/${profileId}/send-invite`,
            null,
            { params: { job_id: jobId } }
          )
          if (sendData.sent) {
            setEmailResult({ ok: true, message: 'Email saved, interview link sent.' })
            onSent?.()
          } else {
            setEmailResult({ ok: false, message: `Email saved, but sending failed: ${sendData.reason}` })
          }
        } catch {
          setEmailResult({ ok: false, message: 'Email saved, but sending failed: something went wrong.' })
        }
      } else {
        setEmailResult({ ok: true, message: 'Email saved.' })
      }
    } catch (err) {
      const body = err.response?.data
      const msg = body?.message ?? body?.detail
      setEmailResult({ ok: false, message: typeof msg === 'string' ? msg : 'Failed to save email.' })
    } finally {
      setSavingEmail(false)
    }
  }

  // Portalled straight to <body> - this modal is opened from cards that use
  // CSS transforms (e.g. TalentMatchCard's hover:-translate-y-0.5) and/or
  // overflow-hidden. A `position: fixed` descendant of a transformed
  // ancestor stops being fixed to the viewport and is clipped/repositioned
  // relative to that ancestor instead  -  which is what caused the reported
  // flicker (the modal fighting the card's hover transform for its
  // containing block). Rendering into `document.body` sidesteps that
  // entirely, regardless of what card this is opened from.
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" aria-hidden="true" />
      <div
        className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Candidate CV"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-border sticky top-0 bg-white z-10">
          <h2 className="font-semibold text-text">Candidate CV</h2>
          <button onClick={onClose} className="p-1.5 rounded-md text-text-muted hover:text-text hover:bg-surface-muted transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-6">
          {loading && (
            <div className="space-y-4 animate-pulse">
              <div className="flex items-center gap-3">
                <div className="w-14 h-14 rounded-full bg-gray-200" />
                <div className="space-y-2 flex-1">
                  <div className="h-4 bg-gray-200 rounded w-1/2" />
                  <div className="h-3 bg-gray-200 rounded w-1/3" />
                </div>
              </div>
              <div className="h-20 bg-gray-200 rounded" />
            </div>
          )}

          {!loading && (error || !profile) && (
            <p className="text-sm text-text-muted text-center py-10">CV not available.</p>
          )}

          {!loading && !error && profile && (
            <>
              {/* Identity */}
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-full bg-brand-blue/10 flex items-center justify-center flex-shrink-0">
                  <Users size={24} className="text-brand-blue" />
                </div>
                <div>
                  <p className="font-semibold text-text text-base">
                    {profile.candidate_name ?? profile.candidate_email ?? 'Unnamed Candidate'}
                  </p>
                  {profile.candidate_current_title && (
                    <p className="text-sm text-text-muted mt-0.5">{profile.candidate_current_title}</p>
                  )}
                  {profile.candidate_email && (
                    <p className="text-xs text-text-muted">{profile.candidate_email}</p>
                  )}
                </div>
              </div>

              {!profile.candidate_email && (
                <div className="rounded-lg border border-dashed border-border p-3 space-y-2">
                  <p className="text-xs text-text-muted">
                    No email on file for this candidate. Enter it manually to send an interview link.
                  </p>
                  <div className="flex items-center gap-2">
                    <input
                      type="email"
                      value={emailInput}
                      onChange={(e) => setEmailInput(e.target.value)}
                      placeholder="candidate@example.com"
                      className="flex-1 text-sm rounded-lg border border-border px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
                    />
                    <button
                      type="button"
                      onClick={handleSaveEmail}
                      disabled={savingEmail || !emailInput.trim()}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-blue text-white hover:bg-brand-blue/90 transition-colors disabled:opacity-50 flex-shrink-0"
                    >
                      {savingEmail ? 'Saving…' : 'Save'}
                    </button>
                  </div>
                  {emailResult && (
                    <p className={cn('text-xs', emailResult.ok ? 'text-green-600' : 'text-red-600')}>
                      {emailResult.message}
                    </p>
                  )}
                </div>
              )}

              {profile.cv_download_url ? (
                <a
                  href={profile.cv_download_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center gap-1.5 w-full rounded-lg border border-brand-blue text-brand-blue px-4 py-2 text-sm font-medium hover:bg-brand-blue/5 transition-colors"
                >
                  <Download size={14} /> Download CV
                </a>
              ) : (
                // Access is fine (we got here) but no file is stored for
                // this submission  -  say so explicitly rather than silently
                // omitting the button, which reads as broken rather than
                // "there's genuinely no file on record."
                <p className="text-xs text-text-muted text-center py-2 border border-dashed border-border rounded-lg">
                  No CV file is on record for this candidate.
                </p>
              )}

              {/* AI Score */}
              {profile.ai_score != null && (
                <div className="rounded-xl border border-border p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-text-muted uppercase tracking-wide flex items-center gap-1.5">
                      <Brain size={12} /> AI Assessment
                    </p>
                    <span
                      className={cn('px-2.5 py-0.5 rounded-full text-xs font-bold border', matchScoreBand(profile.ai_score).className)}
                      title={`Raw score: ${profile.ai_score}/100`}
                    >
                      {matchScoreBand(profile.ai_score).label}
                    </span>
                  </div>
                  {profile.ai_fit_summary && (
                    <p className="text-sm text-text leading-relaxed">{profile.ai_fit_summary}</p>
                  )}
                  {profile.ai_strengths?.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-green-700 uppercase tracking-wide mb-1">Strengths</p>
                      <ul className="space-y-1">
                        {profile.ai_strengths.map((s, i) => (
                          <li key={i} className="text-xs text-text flex items-start gap-1.5">
                            <span className="text-green-500 mt-0.5 flex-shrink-0">✓</span>{s}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {profile.ai_weaknesses?.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-1">Considerations</p>
                      <ul className="space-y-1">
                        {profile.ai_weaknesses.map((w, i) => (
                          <li key={i} className="text-xs text-text flex items-start gap-1.5">
                            <span className="text-amber-500 mt-0.5 flex-shrink-0">·</span>{w}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Source info */}
              <div>
                <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">Source</p>
                <div className="flex items-center gap-2 text-sm text-text">
                  <span className="capitalize">{profile.source}</span>
                  {profile.source_note && <span className="text-text-muted">({profile.source_note})</span>}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body
  )
}
