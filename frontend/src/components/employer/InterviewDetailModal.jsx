import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { X, Brain, FileText, FileCheck2, Loader2, RotateCcw, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import { matchScoreBand } from '@/lib/matchScore'
import { isPlanLimitMessage } from '@/lib/planErrors'
import { endedBadge, isEndedStatus } from '@/lib/strictNotes'
import PlanUpgradeLink from '@/components/PlanUpgradeLink'
import StrictInterviewNotes, { RecordingNotice } from '@/components/employer/StrictInterviewNotes'
import RecordingClips from '@/components/employer/RecordingClips'
import WeightedScoreCard from '@/components/employer/WeightedScoreCard'
import PracticalCaseCard from '@/components/employer/PracticalCaseCard'
import AssessmentRecordCard from '@/components/employer/AssessmentRecordCard'
import ReviewedTag from '@/components/employer/ReviewedTag'
import ScoreReviewPanel from '@/components/employer/ScoreReviewPanel'
import ScorecardView from '@/components/employer/ScorecardView'
import { showsClips } from '@/lib/recordingClips'

// Scoring runs in the background, so after asking for it we check the interview
// every few seconds, for up to two minutes.
export const SCORE_POLL_INTERVAL_MS = 3000
const SCORE_POLL_MAX_TRIES = 40
// While an admin's request to score an interview again is open, the window checks this often.
export const RESCORE_POLL_INTERVAL_MS = 4000

/**
 * RescoreNotice - what the window says about an admin's request to score the interview again: while
 * it runs (the earlier result is hidden, the window updates by itself), and when it did not finish
 * (the earlier result is unchanged and shown). Only an Elevare admin is ever sent `rescore`.
 */
function RescoreNotice({ rescore }) {
  if (rescore.status === 'PENDING' && !rescore.stale) {
    return (
      <div role="status" data-testid="rescore-pending" className="space-y-1 rounded-xl border border-brand-blue/30 bg-blue-50 p-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-brand-blue">
          <Loader2 size={14} className="animate-spin" aria-hidden="true" /> Scoring this interview again…
        </p>
        <p className="text-xs text-text-muted">
          The earlier score, band, ratings, written assessment and scorecard are hidden until the new ones are
          ready. This usually takes a minute or two, and this window updates by itself.
        </p>
      </div>
    )
  }
  const reason = rescore.stale
    ? 'There was no answer after ten minutes, so it was probably lost.'
    : rescore.error || 'Something went wrong.'
  return (
    <div role="alert" data-testid="rescore-failed" className="space-y-1 rounded-xl border border-amber-200 bg-amber-50 p-4">
      <p className="text-sm font-semibold text-amber-900">Scoring this interview again did not finish</p>
      <p className="text-xs text-amber-900">
        {reason} The earlier result is unchanged and is shown below. You can ask for it to be scored again.
      </p>
    </div>
  )
}

/**
 * AssessmentCard - one AI-generated fit score + narrative, used for both
 * the interview assessment and the CV assessment below. The two are
 * computed by entirely independent pipelines (the CV score never feeds
 * into interview scoring or vice versa) and shown side by side so an
 * employer can see where they agree or diverge - e.g. "CV said strong
 * React experience, interview showed shallow answers on it."
 */
function AssessmentCard({
  icon: Icon,
  title,
  score,
  summary,
  strengths,
  weaknesses,
  emptyMessage,
  action,
  reviewed = false,
  scoreHidden = false,
}) {
  // The job's switch has the score left out: the written assessment is still shown, with no score.
  if (scoreHidden && summary) {
    return (
      <div className="rounded-xl border border-border p-4 space-y-2">
        <p className="text-xs font-semibold text-text-muted uppercase tracking-wide flex items-center gap-1.5">
          <Icon size={12} /> {title}
        </p>
        <p className="text-sm text-text leading-relaxed whitespace-pre-wrap">{summary}</p>
      </div>
    )
  }
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
        <span className="inline-flex items-center gap-1.5">
          {reviewed && <ReviewedTag />}
          <span
            className={cn('px-2.5 py-0.5 rounded-full text-xs font-bold border', matchScoreBand(score).className)}
            title={`Raw score: ${score}/100`}
          >
            {matchScoreBand(score).label}
          </span>
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
export default function InterviewDetailModal({ jobId, talentPoolProfileId, candidateName, onClose, onReinstated }) {
  const [rawDetail, setDetail] = useState(null)
  // An admin's request to score the interview again is open: the earlier result is not shown (it is
  // being replaced), only the recording, the transcript and the rest. Everything below reads `detail`.
  const rescore = rawDetail?.rescore ?? null
  const rescoring = rescore?.status === 'PENDING' && !rescore.stale
  const detail = useMemo(
    () =>
      rescoring
        ? {
            ...rawDetail,
            ai_score: null,
            ai_rationale: null,
            reviewed: false,
            score_report: null,
            practical_case: null,
            scorecard: null,
            record: null,
            score_review: null,
          }
        : rawDetail,
    [rawDetail, rescoring]
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  // An interview that ended early can be reinstated: the candidate carries on where they stopped.
  const [reinstating, setReinstating] = useState(false)
  const [reinstateError, setReinstateError] = useState(null)
  const [reinstated, setReinstated] = useState(null)
  // Asking for a score after the fact (for example an interview taken on the
  // Starter plan): 'scoring' while we wait for it, and a message if it fails.
  const [scoring, setScoring] = useState(false)
  const [scoreError, setScoreError] = useState(null)
  const pollTimerRef = useRef(null)

  useEffect(() => () => clearTimeout(pollTimerRef.current), [])

  // While the interview is being scored again, read it every few seconds until the new result is in
  // (or the request has failed), so the window fills in by itself.
  useEffect(() => {
    if (!rescoring) return undefined
    const timer = setInterval(async () => {
      try {
        const { data } = await api.get('/api/v1/interviews/detail', {
          params: { job_id: jobId, talent_pool_profile_id: talentPoolProfileId },
        })
        setDetail(data)
      } catch {
        /* a failed check is not a failed scoring; keep waiting */
      }
    }, RESCORE_POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [rescoring, jobId, talentPoolProfileId])

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

  const handleReinstate = async () => {
    setReinstateError(null)
    setReinstating(true)
    try {
      const { data } = await api.post(`/api/v1/interviews/${talentPoolProfileId}/reinstate`, null, {
        params: { job_id: jobId },
      })
      setReinstated(data)
      onReinstated?.(data)
    } catch (err) {
      setReinstateError(err?.response?.data?.message ?? 'Something went wrong. Please try again.')
    } finally {
      setReinstating(false)
    }
  }

  // The recording arrived and scoring failed for good (a recording that never arrived has no
  // completion time and is recovered from the Interview List instead).
  const scoringFailed = detail?.status === 'FAILED' && Boolean(detail?.completed_at)

  // The candidate takes the interview again from the start (instead of carrying on where they
  // stopped): the attempt's answers and recording are deleted, so it asks first.
  const handleRetake = async () => {
    if (
      !window.confirm(
        'This deletes this attempt’s answers and recording, and sends the candidate a fresh interview with the full time. It cannot be undone. Continue?'
      )
    ) {
      return
    }
    setReinstateError(null)
    setReinstating(true)
    try {
      const { data } = await api.post(`/api/v1/interviews/${talentPoolProfileId}/recover`, null, {
        params: { job_id: jobId, start_over: true },
      })
      setReinstated(data)
      onReinstated?.(data)
    } catch (err) {
      setReinstateError(
        err?.response
          ? (err.response.data?.message ?? 'Something went wrong. Please try again.')
          : 'We could not reach the server. Check your connection and try again.'
      )
    } finally {
      setReinstating(false)
    }
  }

  // Reads the interview again, after an admin set or removed a reviewed score.
  const reloadDetail = async () => {
    const { data } = await api.get('/api/v1/interviews/detail', {
      params: { job_id: jobId, talent_pool_profile_id: talentPoolProfileId },
    })
    setDetail(data)
  }

  const handleScore = async () => {
    // Scoring an interview that ended early closes it: it can no longer be reinstated.
    if (
      isEndedStatus(detail?.status)
      && !window.confirm(
        'Scoring what was recorded closes this interview, so the candidate can no longer carry on. Score it anyway?'
      )
    ) {
      return
    }
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

  // The hiring panel's decision about the candidate, with its reason: recorded by a person, and
  // shown at once in the record. A failure is thrown to the card, which shows the server's words.
  const recordDecision = async (decision, rationale) => {
    const { data } = await api.put(
      `/api/v1/interviews/${talentPoolProfileId}/panel-decision`,
      { decision, rationale },
      { params: { job_id: jobId } }
    )
    setDetail((current) => ({ ...current, record: { ...current.record, panel_decision: data } }))
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

  const ready = !loading && !error && detail && !reinstated

  // On a wide screen the recording stays in view on the left while the questions, answers, scores and
  // transcript scroll on the right; on a phone everything stacks and the whole window scrolls.
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" aria-hidden="true" />
      <div
        className="relative flex w-full max-w-7xl max-h-[92vh] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl lg:h-[90vh]"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Interview detail"
      >
        <div className="flex flex-shrink-0 items-center justify-between px-6 py-4 border-b border-border bg-white">
          <h2 className="font-semibold text-text">
            {candidateName ?? 'Candidate'}'s interview
          </h2>
          <button onClick={onClose} className="p-1.5 rounded-md text-text-muted hover:text-text hover:bg-surface-muted transition-colors" aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <div className={cn('min-h-0 flex-1 overflow-y-auto', ready ? 'lg:overflow-hidden' : 'px-6 py-5 space-y-6')}>
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

          {!loading && !error && detail && reinstated && (
            <div role="status" className="space-y-2 rounded-xl border border-green-200 bg-green-50 p-5 text-center">
              {reinstated.outcome === 'started_over' ? (
                <>
                  <p className="font-semibold text-green-800">The interview was started over</p>
                  <p className="text-sm text-green-800">
                    {reinstated.email_sent
                      ? 'The candidate has been emailed their link. They take the interview again from the start, with the full time.'
                      : 'There is no email address on file for the candidate, so send them the link yourself (Copy link on the Interview List). They take the interview again from the start, with the full time.'}
                  </p>
                </>
              ) : (
                <>
                  <p className="font-semibold text-green-800">The interview was reinstated</p>
                  <p className="text-sm text-green-800">
                    {reinstated.email_sent
                      ? 'The candidate has been emailed the same link. They carry on where they stopped, with the time they had left.'
                      : 'There is no email address on file for the candidate, so send them the link yourself (Copy link on the Interview List). They carry on where they stopped, with the time they had left.'}
                  </p>
                </>
              )}
              <button type="button" onClick={onClose} className="text-xs font-semibold text-green-800 underline">Close</button>
            </div>
          )}

          {ready && (
            <div className="lg:grid lg:h-full lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
              {/* The recording stays in view while the rest is read; the CV assessment sits under it
                  and scrolls on its own */}
              <div className="px-6 pt-5 lg:flex lg:min-h-0 lg:flex-col lg:overflow-hidden lg:border-r lg:border-border lg:pb-5">
              <div className="space-y-3 lg:max-h-[65%] lg:flex-shrink-0 lg:overflow-y-auto">
              {showsClips(detail.recordings, detail.video_url) ? (
                <RecordingClips recordings={detail.recordings} />
              ) : detail.video_url ? (
                <video
                  src={detail.video_url}
                  controls
                  className="w-full rounded-xl overflow-hidden bg-black aspect-video"
                >
                  Your browser does not support inline video playback.
                </video>
              ) : detail.strict?.recording_pending ? (
                <RecordingNotice strict={detail.strict} />
              ) : (
                <p className="text-xs text-text-muted text-center py-6 border border-dashed border-border rounded-lg">
                  No recording is available for this interview.
                </p>
              )}
              {/* Says "being put together" or "may be only part": next to the video, or, for a
                  reinstated interview whose latest pieces are being joined, under the earlier clips. */}
              {(detail.video_url || showsClips(detail.recordings, detail.video_url)) && (
                <RecordingNotice strict={detail.strict} />
              )}
              </div>
              <div className="mt-4 pb-5 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:pb-0">
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
              </div>

              <div className="space-y-6 px-6 py-5 lg:overflow-y-auto">
              {isEndedStatus(detail.status) && (
                <div className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-4">
                  <p className="text-sm font-semibold text-amber-900">
                    {endedBadge(detail.status)}. It has not been scored.
                  </p>
                  <p className="text-xs text-amber-900">
                    Look at the recording and the notes below, then decide. If you reinstate it, the
                    candidate is emailed the same link and carries on where they stopped, with the time
                    they had left and their warnings started again. Nothing more is charged.
                  </p>
                  <button
                    type="button"
                    onClick={handleReinstate}
                    disabled={reinstating}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-brand-blue px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-blue/90 disabled:opacity-50"
                  >
                    {reinstating ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />}
                    {reinstating ? 'Reinstating…' : 'Reinstate this interview'}
                  </button>
                  <div className="space-y-1 border-t border-amber-200 pt-2">
                    <p className="text-xs text-amber-900">
                      Is the recording missing or empty? Have the candidate take the interview again from
                      the start instead. This deletes this attempt&apos;s answers and recording.
                    </p>
                    <button
                      type="button"
                      onClick={handleRetake}
                      disabled={reinstating}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-amber-400 bg-white px-3 py-1.5 text-xs font-semibold text-amber-900 transition-colors hover:bg-amber-100 disabled:opacity-50"
                    >
                      Have them retake it
                    </button>
                  </div>
                  {reinstateError && <p role="alert" className="text-xs text-red-600">{reinstateError}</p>}
                </div>
              )}

              {/* A strict interview: the rules accepted, how it went on the screen, each answer. */}
              <StrictInterviewNotes strict={detail.strict} />

              {/* An admin's request to score the interview again: running, or it did not finish */}
              {rescore && <RescoreNotice rescore={rescore} />}

              {/* The practical case, scored on its own and never part of the weighted score */}
              {detail.practical_case && <PracticalCaseCard report={detail.practical_case} />}

              {/* The interview assessment, at the full width of this column (the CV assessment is under the video) */}
              <div>
                {/* A job with a scoring profile: the weighted table, the total or "incomplete",
                    and the suggested band, instead of the single score card. */}
                {detail.score_report ? (
                  <WeightedScoreCard report={detail.score_report}>
                    {detail.ai_rationale && (
                      <p className="whitespace-pre-wrap text-sm leading-relaxed text-text">{detail.ai_rationale}</p>
                    )}
                  </WeightedScoreCard>
                ) : detail.writeup_hidden || rescoring ? null : (
                <AssessmentCard
                  icon={Brain}
                  title="Interview Assessment"
                  score={detail.ai_score}
                  reviewed={detail.reviewed}
                  scoreHidden={detail.scores_hidden || detail.score_number_hidden}
                  summary={detail.ai_rationale}
                  emptyMessage={
                    isEndedStatus(detail.status)
                      ? 'This interview ended early, so it has not been scored. Reinstate it so the candidate can finish, or score what was recorded.'
                      : 'No score is available for this interview. It may not be included in your plan, scoring may still be running, or it could not be completed. Please review the recording and transcript directly.'
                  }
                  action={
                    // Offered once the interview is finished but has no score.
                    // While it is being scored (or we are waiting for it), say so instead.
                    scoring ? (
                      <p className="text-xs text-text-muted inline-flex items-center gap-1.5">
                        <Loader2 size={13} className="animate-spin" />
                        Scoring this interview…
                      </p>
                    ) : detail.status === 'SCORED' || detail.status === 'UPLOADED' || isEndedStatus(detail.status) || scoringFailed ? (
                      <div className="space-y-1.5">
                        <button
                          type="button"
                          onClick={handleScore}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-blue text-white hover:bg-brand-blue/90 transition-colors"
                        >
                          <Sparkles size={13} />
                          {isEndedStatus(detail.status) ? 'Score what was recorded' : scoringFailed ? 'Retry scoring' : 'Generate score'}
                        </button>
                        {scoringFailed && (
                          <p className="text-xs text-text-muted">
                            Scoring did not finish. If its credit was given back, retrying uses one again.
                          </p>
                        )}
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
                )}
              </div>

              {/* The scorecard as Elevare prints it, with a button that prints it (or saves a PDF) */}
              {detail.scorecard && (
                <ScorecardView
                  scorecard={detail.scorecard}
                  candidateName={candidateName ?? 'Candidate'}
                  role={detail.record?.role}
                  date={detail.completed_at}
                />
              )}

              {/* Only an Elevare admin gets this from the server: set the score in place of the
                  system's, with the system's own score and the history kept here */}
              {detail.score_review && detail.status === 'SCORED' && (
                <ScoreReviewPanel
                  key={`${detail.ai_score}-${detail.reviewed}`}
                  jobId={jobId}
                  talentPoolProfileId={talentPoolProfileId}
                  detail={detail}
                  onChanged={reloadDetail}
                />
              )}

              {/* The candidate assessment record: the header, the top three strengths and gaps,
                  what to verify, and the hiring panel's own decision with its sign-off */}
              {detail.record && (
                <AssessmentRecordCard
                  record={detail.record}
                  gapsHidden={detail.gaps_hidden}
                  onDecide={recordDecision}
                  suggestedBand={detail.score_report?.complete ? detail.score_report.band : null}
                  suggestedScore={detail.score_report?.complete ? detail.score_report.score : null}
                  blockedReason={
                    detail.status === 'UPLOADED' || detail.status === 'SCORED' || isEndedStatus(detail.status)
                      ? null
                      : 'The interview has not finished yet, so there is nothing to decide on.'
                  }
                />
              )}

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
                      any score is based on it. Please check the video.
                    </p>
                  )}
                  {detail.transcript_check === 'UNAVAILABLE' && (
                    <p className="text-xs text-text-muted mb-2">
                      This transcript could not be checked against the recording.
                    </p>
                  )}
                  <div className="max-h-64 overflow-y-auto lg:max-h-none text-sm text-text leading-relaxed whitespace-pre-wrap rounded-lg border border-border p-3 bg-surface-muted">
                    {detail.transcript}
                  </div>
                </div>
              )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  )
}
