import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { X, Brain, FileText, FileCheck2, Loader2, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import { matchScoreBand } from '@/lib/matchScore'
import { isPlanLimitMessage } from '@/lib/planErrors'
import PlanUpgradeLink from '@/components/PlanUpgradeLink'

// Scoring runs in the background, so after asking for it we check the interview
// every few seconds, for up to two minutes.
export const SCORE_POLL_INTERVAL_MS = 3000
const SCORE_POLL_MAX_TRIES = 40

/**
 * AssessmentCard - one AI-generated fit score + narrative, used for both
 * the interview assessment and the CV assessment below. The two are
 * computed by entirely independent pipelines (the CV score never feeds
 * into interview scoring or vice versa) and shown side by side so an
 * employer can see where they agree or diverge - e.g. "CV said strong
 * React experience, interview showed shallow answers on it."
 */
function AssessmentCard({ icon: Icon, title, score, summary, strengths, weaknesses, emptyMessage, action }) {
  if (score == null) {
    return (
      <div className="rounded-xl border border-dashed border-border p-4">
        <p className="text-xs font-semibold text-text-muted uppercase tracking-wide flex items-center gap-1.5 mb-2">
          <Icon size={12} /> {title}
        </p>
        <p className="text-xs text-text-muted">{emptyMessage}</p>
        {action && <div className="mt-3">{action}</div>}
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-border p-4 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-text-muted uppercase tracking-wide flex items-center gap-1.5">
          <Icon size={12} /> {title}
        </p>
        <span
          className={cn('px-2.5 py-0.5 rounded-full text-xs font-bold border', matchScoreBand(score).className)}
          title={`Raw score: ${score}/100`}
        >
          {matchScoreBand(score).label}
        </span>
      </div>
      {summary && (
        <p className="text-sm text-text leading-relaxed whitespace-pre-wrap">{summary}</p>
      )}
      {strengths?.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-green-700 uppercase tracking-wide mb-1">Strengths</p>
          <ul className="space-y-0.5">
            {strengths.map((s, i) => (
              <li key={i} className="text-xs text-text flex items-start gap-1.5">
                <span className="text-green-500 mt-0.5 flex-shrink-0">✓</span>{s}
              </li>
            ))}
          </ul>
        </div>
      )}
      {weaknesses?.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-amber-700 uppercase tracking-wide mb-1">Considerations</p>
          <ul className="space-y-0.5">
            {weaknesses.map((w, i) => (
              <li key={i} className="text-xs text-text flex items-start gap-1.5">
                <span className="text-amber-500 mt-0.5 flex-shrink-0">·</span>{w}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

/**
 * InterviewDetailModal - employer view of one candidate's completed AI
 * video interview: inline video playback (no download, no new tab), the
 * interview and CV assessments side by side, and the transcript. Fetched
 * by (job_id, talent_pool_profile_id) - the natural key already on hand
 * from the Interview List row this is opened from.
 */
export default function InterviewDetailModal({ jobId, talentPoolProfileId, candidateName, onClose }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  // Asking for a score after the fact (for example an interview taken on the
  // Starter plan): 'scoring' while we wait for it, and a message if it fails.
  const [scoring, setScoring] = useState(false)
  const [scoreError, setScoreError] = useState(null)
  const pollTimerRef = useRef(null)

  useEffect(() => () => clearTimeout(pollTimerRef.current), [])

  // Checks the interview every few seconds until it is no longer being
  // processed. Used both after asking for a score and when the window is opened
  // on an interview that is already being scored.
  const pollForScore = useCallback(() => {
    const check = (attempt) => {
      pollTimerRef.current = setTimeout(async () => {
        try {
          const { data } = await api.get('/api/v1/interviews/detail', {
            params: { job_id: jobId, talent_pool_profile_id: talentPoolProfileId },
          })
          setDetail(data)
          if (data.status !== 'UPLOADED') {
            // Finished. A score means it worked; no score means scoring failed again.
            setScoring(false)
            if (data.ai_score == null) {
              setScoreError('We could not score this interview. Please try again in a few minutes.')
            }
            return
          }
        } catch {
          /* a failed check is not a failed scoring; keep waiting */
        }
        if (attempt >= SCORE_POLL_MAX_TRIES) {
          setScoring(false)
          setScoreError('Scoring is taking longer than usual. Close this window and check back shortly.')
          return
        }
        check(attempt + 1)
      }, SCORE_POLL_INTERVAL_MS)
    }
    clearTimeout(pollTimerRef.current)
    check(1)
  }, [jobId, talentPoolProfileId])

  const handleScore = async () => {
    setScoreError(null)
    setScoring(true)
    try {
      await api.post('/api/v1/interviews/score', null, {
        params: { job_id: jobId, talent_pool_profile_id: talentPoolProfileId },
      })
      pollForScore()
    } catch (err) {
      setScoring(false)
      setScoreError(err?.response?.data?.message ?? 'Something went wrong. Please try again.')
    }
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(false)
    api.get('/api/v1/interviews/detail', {
      params: { job_id: jobId, talent_pool_profile_id: talentPoolProfileId },
    })
      .then(({ data }) => {
        if (cancelled) return
        setDetail(data)
        // Opened while the interview is still being scored: wait for the
        // result instead of showing a spinner that never changes.
        if (data.status === 'UPLOADED') {
          setScoring(true)
          pollForScore()
        }
      })
      .catch(() => { if (!cancelled) setError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [jobId, talentPoolProfileId, pollForScore])

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" aria-hidden="true" />
      <div
        className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Interview detail"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-border sticky top-0 bg-white z-10">
          <h2 className="font-semibold text-text">
            {candidateName ?? 'Candidate'}'s AI interview
          </h2>
          <button onClick={onClose} className="p-1.5 rounded-md text-text-muted hover:text-text hover:bg-surface-muted transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-6">
          {loading && (
            <div className="space-y-4 animate-pulse">
              <div className="w-full aspect-video bg-gray-200 rounded-xl" />
              <div className="h-4 bg-gray-200 rounded w-1/2" />
              <div className="h-20 bg-gray-200 rounded" />
            </div>
          )}

          {!loading && (error || !detail) && (
            <p className="text-sm text-text-muted text-center py-10">Interview detail not available.</p>
          )}

          {!loading && !error && detail && (
            <>
              {detail.video_url ? (
                <video
                  src={detail.video_url}
                  controls
                  className="w-full rounded-xl overflow-hidden bg-black aspect-video"
                >
                  Your browser does not support inline video playback.
                </video>
              ) : (
                <p className="text-xs text-text-muted text-center py-6 border border-dashed border-border rounded-lg">
                  No recording is available for this interview.
                </p>
              )}

              {/* Interview + CV assessments, side by side */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <AssessmentCard
                  icon={Brain}
                  title="Interview Assessment"
                  score={detail.ai_score}
                  summary={detail.ai_rationale}
                  emptyMessage="No AI score is available for this interview. It may not be included in your plan, scoring may still be running, or it could not be completed. Please review the recording and transcript directly."
                  action={
                    // Offered once the interview is finished but has no score.
                    // While it is being scored (or we are waiting for it), say so instead.
                    scoring ? (
                      <p className="text-xs text-text-muted inline-flex items-center gap-1.5">
                        <Loader2 size={13} className="animate-spin" />
                        Scoring this interview…
                      </p>
                    ) : detail.status === 'SCORED' || detail.status === 'UPLOADED' ? (
                      <div className="space-y-1.5">
                        <button
                          type="button"
                          onClick={handleScore}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-blue text-white hover:bg-brand-blue/90 transition-colors"
                        >
                          <Sparkles size={13} />
                          Generate AI score
                        </button>
                        {scoreError && (
                          <p className="text-xs text-red-600">
                            {scoreError}
                            {isPlanLimitMessage(scoreError) && <PlanUpgradeLink />}
                          </p>
                        )}
                      </div>
                    ) : null
                  }
                />
                <AssessmentCard
                  icon={FileCheck2}
                  title="CV Assessment"
                  score={detail.cv_score}
                  summary={detail.cv_fit_summary}
                  strengths={detail.cv_strengths}
                  weaknesses={detail.cv_weaknesses}
                  emptyMessage="No CV fit score is available for this candidate on this job."
                />
              </div>

              {/* Transcript */}
              {detail.transcript && (
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2 flex items-center gap-1.5">
                    <FileText size={12} /> Transcript
                  </p>
                  {detail.transcript_check === 'MISMATCH' && (
                    <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-2.5 mb-2">
                      The transcript sent from the candidate&apos;s device did not match the recording, so
                      this is an automatic transcript of the recording instead. It has no speaker labels, and
                      any AI score is based on it. Please check the video.
                    </p>
                  )}
                  {detail.transcript_check === 'UNAVAILABLE' && (
                    <p className="text-xs text-text-muted mb-2">
                      This transcript could not be checked against the recording.
                    </p>
                  )}
                  <div className="max-h-64 overflow-y-auto text-sm text-text leading-relaxed whitespace-pre-wrap rounded-lg border border-border p-3 bg-surface-muted">
                    {detail.transcript}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>,
    document.body
  )
}
