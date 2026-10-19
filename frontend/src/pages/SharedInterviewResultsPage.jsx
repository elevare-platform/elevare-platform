import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { ChevronDown, ChevronUp, MessageCircleQuestion, User } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import { parseAssessment } from '@/lib/interviewAssessment'

// What the client is told about each candidate's interview.
const STATUS = {
  COMPLETED: { label: 'Completed', className: 'bg-green-50 text-green-700 border-green-200' },
  IN_PROGRESS: { label: 'Interview in progress', className: 'bg-blue-50 text-blue-700 border-blue-200' },
  INVITED: { label: 'Invited', className: 'bg-blue-50 text-blue-700 border-blue-200' },
  NOT_COMPLETED: { label: 'Not completed', className: 'bg-amber-50 text-amber-800 border-amber-200' },
  NOT_INVITED: { label: 'Not interviewed yet', className: 'bg-gray-100 text-gray-600 border-gray-200' },
}

// Why a link does not open, by the error code the server sends.
const LINK_PROBLEMS = {
  SHARE_LINK_EXPIRED: {
    title: 'This link has expired',
    text: 'Links stop working after 3 days. Please ask for a new one.',
  },
  SHARE_LINK_REVOKED: {
    title: 'This link is no longer active',
    text: 'It was replaced or withdrawn. Please ask for the latest link.',
  },
  SHARE_LINK_NOT_FOUND: {
    title: 'This link is not valid',
    text: 'It may have been copied incompletely. Please ask for a new one.',
  },
}

function scoreColour(score) {
  if (score == null) return 'bg-gray-100 text-gray-500'
  if (score <= 40) return 'bg-red-100 text-red-600'
  if (score <= 70) return 'bg-amber-100 text-amber-700'
  return 'bg-green-100 text-green-700'
}

function formatDate(iso, options) {
  return iso ? new Date(iso).toLocaleDateString('en-GB', options) : null
}

function ScoreBadge({ label, score }) {
  return (
    <div className="text-center">
      <span
        className={cn(
          'w-11 h-11 rounded-full flex items-center justify-center text-sm font-bold mx-auto',
          scoreColour(score),
        )}
      >
        {score ?? 'N/A'}
      </span>
      <span className="block text-[10px] text-text-muted mt-1">{label}</span>
    </div>
  )
}

function BulletList({ title, items, tone }) {
  if (!items?.length) return null
  return (
    <div>
      <p className={cn('text-xs font-semibold mb-1', tone === 'good' ? 'text-green-700' : 'text-amber-700')}>
        {title}
      </p>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="text-xs text-text flex items-start gap-2">
            <span className={tone === 'good' ? 'text-green-500' : 'text-amber-500'}>•</span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Assessment({ title, score, summary, strengths, weaknesses, sections, emptyText }) {
  const hasContent = score != null || summary?.length || strengths?.length || weaknesses?.length || sections?.length
  return (
    <div className="rounded-lg border border-border bg-white p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-sm font-semibold text-text">{title}</h4>
        {score != null && (
          <span className={cn('px-2 py-0.5 rounded-full text-xs font-bold', scoreColour(score))}>{score}</span>
        )}
      </div>
      {!hasContent && <p className="text-xs text-text-muted">{emptyText}</p>}
      {summary?.map((paragraph, i) => (
        <p key={i} className="text-sm text-text leading-relaxed">{paragraph}</p>
      ))}
      <BulletList title="Strengths" items={strengths} tone="good" />
      <BulletList title="Considerations" items={weaknesses} tone="warn" />
      {sections?.map((section) => (
        <BulletList
          key={section.title}
          // The CV column says "Considerations"; the interview column says the same.
          title={section.title === 'Weaknesses' ? 'Considerations' : section.title}
          items={section.items}
          tone={section.title === 'Strengths' ? 'good' : 'warn'}
        />
      ))}
    </div>
  )
}

// The questions the AI asked, numbered, so they are the first thing read.
function Questions({ questions }) {
  if (!questions.length) return null
  return (
    <div className="rounded-lg border border-brand-blue/30 bg-blue-50/50 p-4">
      <h4 className="text-sm font-semibold text-text flex items-center gap-2 mb-2">
        <MessageCircleQuestion size={16} className="text-brand-blue" aria-hidden="true" />
        Questions the AI asked
      </h4>
      <ol className="space-y-1.5 list-decimal pl-5">
        {questions.map((question, i) => (
          <li key={i} className="text-sm text-text font-medium">{question}</li>
        ))}
      </ol>
    </div>
  )
}

// The whole conversation, each AI turn set apart from the candidate's answer.
function Conversation({ turns }) {
  return (
    <div className="space-y-2">
      {turns.map((turn, i) =>
        turn.speaker === 'AI' ? (
          <div key={i} className="border-l-4 border-brand-blue bg-blue-50/60 rounded-r-lg px-3 py-2">
            <p className="text-[11px] font-semibold text-brand-blue mb-0.5">AI interviewer</p>
            <p className="text-sm font-semibold text-text whitespace-pre-wrap">{turn.text}</p>
          </div>
        ) : (
          <div key={i} className="pl-4 pr-1 py-1">
            <p className="text-[11px] font-semibold text-text-muted mb-0.5">Candidate</p>
            <p className="text-sm text-text whitespace-pre-wrap">{turn.text}</p>
          </div>
        ),
      )}
    </div>
  )
}

function CandidateCard({ candidate, rank, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen)
  const status = STATUS[candidate.status] ?? STATUS.NOT_INVITED
  const interview = parseAssessment(candidate.interview_assessment)
  const interviewed = candidate.status === 'COMPLETED'
  const hasDetail =
    interviewed || candidate.cv_score != null || candidate.cv_summary || candidate.cv_strengths?.length

  return (
    <div className="rounded-xl border border-border bg-white overflow-hidden">
      <button
        type="button"
        onClick={() => hasDetail && setOpen((v) => !v)}
        aria-expanded={hasDetail ? open : undefined}
        className="w-full flex items-center gap-4 p-4 text-left"
      >
        <span className="w-7 h-7 rounded-full bg-surface-muted text-text-muted text-xs font-semibold flex items-center justify-center flex-shrink-0">
          {rank}
        </span>
        <span className="w-10 h-10 rounded-full bg-brand-blue/10 flex items-center justify-center flex-shrink-0" aria-hidden="true">
          <User size={18} className="text-brand-blue" />
        </span>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-text text-sm">{candidate.name}</p>
          {candidate.current_title && (
            <p className="text-xs text-text-muted line-clamp-1">{candidate.current_title}</p>
          )}
          <span className={cn('inline-block mt-1 px-2 py-0.5 rounded-full border text-[11px] font-medium', status.className)}>
            {status.label}
          </span>
        </div>
        {interviewed && <ScoreBadge label="Interview" score={candidate.interview_score} />}
        {candidate.cv_score != null && <ScoreBadge label="CV" score={candidate.cv_score} />}
        {hasDetail && (open ? <ChevronUp size={16} className="text-text-muted" /> : <ChevronDown size={16} className="text-text-muted" />)}
      </button>

      {open && hasDetail && (
        <div className="border-t border-border px-4 py-4 bg-surface-muted space-y-4">
          {candidate.video_url && (
            <div>
              <video controls preload="metadata" src={candidate.video_url} className="w-full rounded-lg bg-black" />
              <p className="text-[11px] text-text-muted mt-1">
                The video link is refreshed each time this page opens and stops working after about 15
                minutes. Reload the page if it stops playing.
              </p>
            </div>
          )}

          <Questions questions={candidate.questions ?? []} />

          <div className="grid gap-3 sm:grid-cols-2">
            {interviewed && (
              <Assessment
                title="Interview assessment"
                score={candidate.interview_score}
                summary={interview.summary}
                sections={interview.sections}
                emptyText="No AI assessment is available for this interview."
              />
            )}
            <Assessment
              title="CV assessment"
              score={candidate.cv_score}
              summary={candidate.cv_summary ? [candidate.cv_summary] : []}
              strengths={candidate.cv_strengths}
              weaknesses={candidate.cv_weaknesses}
              emptyText="No CV assessment is available for this candidate on this job."
            />
          </div>

          {interviewed && (
            <div>
              <h4 className="text-sm font-semibold text-text mb-2">Interview conversation</h4>
              {candidate.transcript_note && (
                <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-2.5 mb-2">
                  {candidate.transcript_note}
                </p>
              )}
              {candidate.turns?.length > 0 ? (
                <Conversation turns={candidate.turns} />
              ) : candidate.transcript ? (
                <div className="text-sm text-text leading-relaxed whitespace-pre-wrap rounded-lg border border-border p-3 bg-white">
                  {candidate.transcript}
                </div>
              ) : (
                <p className="text-xs text-text-muted">No transcript is available.</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Message({ title, text }) {
  return (
    <div className="min-h-screen bg-surface-muted flex items-center justify-center px-4">
      <div className="text-center max-w-sm">
        <p className="text-2xl font-bold text-text mb-2">{title}</p>
        <p className="text-sm text-text-muted">{text}</p>
      </div>
    </div>
  )
}

/**
 * The page behind a job's "interview results" link: read-only, no login. Shows each
 * candidate on the job's interview list with the interview and CV assessments, the
 * recording, the questions the AI asked and the conversation.
 */
export default function SharedInterviewResultsPage() {
  const { token } = useParams()
  const [data, setData] = useState(null)
  const [problem, setProblem] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showAllFocus, setShowAllFocus] = useState(false)

  useEffect(() => {
    let cancelled = false
    api.get(`/api/v1/public/interview-results/${token}`)
      .then(({ data: body }) => { if (!cancelled) setData(body) })
      .catch((err) => {
        if (cancelled) return
        const code = err.response?.data?.code
        setProblem(
          LINK_PROBLEMS[code] ?? {
            title: 'Something went wrong',
            text: 'We could not load these results. Please try again in a moment.',
          },
        )
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [token])

  const noIndex = (
    <Helmet>
      <title>Interview results | Elevare Human Solutions</title>
      {/* Personal data and recordings: never for search engines. */}
      <meta name="robots" content="noindex, nofollow" />
    </Helmet>
  )

  if (loading) {
    return (
      <div className="min-h-screen bg-surface-muted flex items-center justify-center">
        {noIndex}
        <div className="w-8 h-8 border-4 border-brand-blue border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (problem) {
    return (
      <>
        {noIndex}
        <Message title={problem.title} text={problem.text} />
      </>
    )
  }

  const expiry = formatDate(data.expires_at, { day: 'numeric', month: 'long', year: 'numeric' })
  const focus = data.interview_focus ?? ''
  const longFocus = focus.length > 400

  return (
    <div className="min-h-screen bg-surface-muted">
      {noIndex}
      <div className="max-w-3xl mx-auto px-4 py-10 space-y-6">
        <div className="space-y-1">
          <p className="text-xs font-semibold text-text-muted">Interview results</p>
          <h1 className="text-2xl font-bold text-text font-sans">{data.job_title}</h1>
          {data.company_name && <p className="text-sm text-text-muted">{data.company_name}</p>}
          <p className="text-xs text-text-muted">
            {data.completed_count} of {data.total_candidates} interviews completed
            {expiry && <> · This link expires on {expiry}</>}
          </p>
        </div>

        {focus && (
          <div className="rounded-xl border border-border bg-white p-4">
            <h2 className="text-sm font-semibold text-text mb-1">What the AI was asked to cover</h2>
            <p className={cn('text-sm text-text whitespace-pre-wrap', longFocus && !showAllFocus && 'line-clamp-4')}>
              {focus}
            </p>
            {longFocus && (
              <button
                type="button"
                onClick={() => setShowAllFocus((v) => !v)}
                className="text-xs text-brand-blue hover:underline mt-1"
              >
                {showAllFocus ? 'Show less' : 'Show all'}
              </button>
            )}
          </div>
        )}

        {data.candidates.length === 0 ? (
          <p className="text-sm text-text-muted text-center py-10">No candidates on this interview list yet.</p>
        ) : (
          <div className="space-y-3">
            {data.candidates.map((candidate, i) => (
              <CandidateCard key={i} candidate={candidate} rank={i + 1} defaultOpen={i === 0 && candidate.status === 'COMPLETED'} />
            ))}
          </div>
        )}

        {data.truncated && (
          <p className="text-xs text-text-muted text-center">
            Showing the first {data.candidates.length} of {data.total_candidates} candidates.
          </p>
        )}

        <p className="text-xs text-text-muted text-center pt-4">
          This page contains personal information and recordings shared for hiring purposes. Please
          do not forward it.
        </p>
        <p className="text-xs text-text-muted text-center">Powered by Elevare Human Solutions</p>
      </div>
    </div>
  )
}
