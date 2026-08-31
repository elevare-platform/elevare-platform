import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X, Brain, FileText, FileCheck2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import { matchScoreBand } from '@/lib/matchScore'

/**
 * AssessmentCard - one AI-generated fit score + narrative, used for both
 * the interview assessment and the CV assessment below. The two are
 * computed by entirely independent pipelines (the CV score never feeds
 * into interview scoring or vice versa) and shown side by side so an
 * employer can see where they agree or diverge - e.g. "CV said strong
 * React experience, interview showed shallow answers on it."
 */
function AssessmentCard({ icon: Icon, title, score, summary, strengths, weaknesses, emptyMessage }) {
  if (score == null) {
    return (
      <div className="rounded-xl border border-dashed border-border p-4">
        <p className="text-xs font-semibold text-text-muted uppercase tracking-wide flex items-center gap-1.5 mb-2">
          <Icon size={12} /> {title}
        </p>
        <p className="text-xs text-text-muted">{emptyMessage}</p>
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

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(false)
    api.get('/api/v1/interviews/detail', {
      params: { job_id: jobId, talent_pool_profile_id: talentPoolProfileId },
    })
      .then(({ data }) => { if (!cancelled) setDetail(data) })
      .catch(() => { if (!cancelled) setError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [jobId, talentPoolProfileId])

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
                  emptyMessage="AI scoring isn't available for this interview because it's not included in your plan or scoring hasn't finished yet."
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
