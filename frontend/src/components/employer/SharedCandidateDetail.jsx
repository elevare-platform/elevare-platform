import { useState } from 'react'
import { ArrowLeft, ChevronLeft, ChevronRight, MessageCircleQuestion } from 'lucide-react'
import { cn } from '@/lib/utils'
import { parseAssessment } from '@/lib/interviewAssessment'
import { showsClips } from '@/lib/recordingClips'
import StrictInterviewNotes, { RecordingNotice } from '@/components/employer/StrictInterviewNotes'
import RecordingClips from '@/components/employer/RecordingClips'
import WeightedScoreCard from '@/components/employer/WeightedScoreCard'
import PracticalCaseCard from '@/components/employer/PracticalCaseCard'
import AssessmentRecordCard from '@/components/employer/AssessmentRecordCard'
import ReviewedTag from '@/components/employer/ReviewedTag'
import ScorecardView from '@/components/employer/ScorecardView'
import { BAND_NAMES, BAND_STYLE } from '@/lib/scoringProfile'
import { STATUS, scoreColour } from '@/lib/sharedResults'

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

function Assessment({ title, score, summary, strengths, weaknesses, sections, emptyText, reviewed = false }) {
  const hasContent = score != null || summary?.length || strengths?.length || weaknesses?.length || sections?.length
  return (
    <div className="rounded-lg border border-border bg-white p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-sm font-semibold text-text">{title}</h4>
        {score != null && (
          <span className="inline-flex items-center gap-1.5">
            {reviewed && <ReviewedTag />}
            <span className={cn('px-2 py-0.5 rounded-full text-xs font-bold', scoreColour(score))}>{score}</span>
          </span>
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
        Questions asked
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
            <p className="text-[11px] font-semibold text-brand-blue mb-0.5">Interviewer</p>
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

// The recording, which stays beside the tabs on a wide screen so it can be watched while reading.
function Recording({ candidate }) {
  const clips = showsClips(candidate.recordings, candidate.video_url)
  if (clips) {
    return (
      <div>
        <RecordingClips recordings={candidate.recordings} videoClassName="w-full rounded-lg bg-black" />
        <p className="text-[11px] text-text-muted mt-1">
          The video links are refreshed each time this page opens and stop working after about 15
          minutes. Reload the page if one stops playing.
        </p>
        <RecordingNotice strict={candidate.strict} />
      </div>
    )
  }
  if (candidate.video_url) {
    return (
      <div>
        <video controls preload="metadata" src={candidate.video_url} className="w-full rounded-lg bg-black" />
        <p className="text-[11px] text-text-muted mt-1">
          The video link is refreshed each time this page opens and stops working after about 15
          minutes. Reload the page if it stops playing.
        </p>
        <RecordingNotice strict={candidate.strict} />
      </div>
    )
  }
  return <RecordingNotice strict={candidate.strict} />
}

function Tabs({ tabs, active, onChange }) {
  return (
    <div role="tablist" aria-label="Candidate details" className="flex flex-wrap gap-1.5">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          id={`shared-tab-${tab.id}`}
          aria-selected={active === tab.id}
          aria-controls="shared-tabpanel"
          onClick={() => onChange(tab.id)}
          className={cn(
            'px-3 py-1.5 rounded-full text-xs font-semibold transition-colors',
            active === tab.id
              ? 'bg-brand-blue text-white'
              : 'bg-white border border-border text-text-muted hover:text-text',
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}

/**
 * One candidate on the shared results page: the recording beside tabs for the summary, the scores,
 * the conversation and the assessment record. Previous and next step through the candidates
 * currently listed; "Back to all candidates" returns to the list on a phone. Mount it with the
 * candidate as `key` so it opens on the Summary tab each time.
 */
export default function SharedCandidateDetail({ candidate, rank, position, onPrevious, onNext, onBack }) {
  const interview = parseAssessment(candidate.interview_assessment)
  const interviewed = candidate.status === 'COMPLETED'
  // An interview that ended early has a recording, answers and notes worth opening, but no
  // assessment of the interview.
  const endedEarly = candidate.status === 'ENDED'
  const status = STATUS[candidate.status] ?? STATUS.NOT_INVITED
  const report = candidate.score_report

  const tabs = [{ id: 'summary', label: 'Summary' }]
  if (candidate.scorecard) tabs.push({ id: 'scorecard', label: 'Scorecard' })
  if (report || candidate.practical_case) tabs.push({ id: 'scores', label: 'Scores' })
  if (interviewed || endedEarly) tabs.push({ id: 'conversation', label: 'Conversation' })
  if (candidate.record) tabs.push({ id: 'record', label: 'Assessment record' })
  const [active, setActive] = useState('summary')

  // With no video and no recording notice there is no left column, and the tabs take the width.
  const hasRecording =
    showsClips(candidate.recordings, candidate.video_url) ||
    Boolean(candidate.video_url) ||
    Boolean(candidate.strict?.recording_pending || candidate.strict?.recording_partial)
  const lone = !hasRecording

  return (
    <section aria-label={`${candidate.name}, interview details`} className="rounded-xl border border-border bg-white overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-border p-4">
        <button
          type="button"
          onClick={onBack}
          className="lg:hidden inline-flex items-center gap-1 text-xs font-semibold text-brand-blue"
        >
          <ArrowLeft size={14} aria-hidden="true" /> Back to all candidates
        </button>
        <div className="flex-1 min-w-0">
          <h2 className="font-semibold text-text break-words">
            <span className="text-text-muted font-medium">{rank}.</span> {candidate.name}
          </h2>
          <div className="flex flex-wrap items-center gap-2 mt-0.5">
            {candidate.current_title && <span className="text-xs text-text-muted">{candidate.current_title}</span>}
            <span className={cn('inline-block px-2 py-0.5 rounded-full border text-[11px] font-medium', status.className)}>
              {status.label}
            </span>
            {report?.complete && (
              <span
                className={cn(
                  'inline-block px-2 py-0.5 rounded-full border text-[11px] font-medium',
                  BAND_STYLE[report.band] ?? BAND_STYLE[BAND_NAMES.hold],
                )}
              >
                {report.band}
              </span>
            )}
            {(candidate.interview_reviewed || report?.reviewed) && <ReviewedTag />}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {position && <span className="text-xs text-text-muted">Candidate {position.index} of {position.total}</span>}
          <button
            type="button"
            onClick={onPrevious}
            disabled={!onPrevious}
            aria-label="Previous candidate"
            className="p-1.5 rounded-lg border border-border text-text-muted hover:text-text disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ChevronLeft size={16} aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={onNext}
            disabled={!onNext}
            aria-label="Next candidate"
            className="p-1.5 rounded-lg border border-border text-text-muted hover:text-text disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ChevronRight size={16} aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className={cn('bg-surface-muted p-4 grid gap-4', !lone && 'xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]')}>
        {!lone && (
          <div className="xl:sticky xl:top-4 xl:self-start">
            <Recording candidate={candidate} />
          </div>
        )}

        <div className="space-y-4 min-w-0">
          {tabs.length > 1 && <Tabs tabs={tabs} active={active} onChange={setActive} />}

          <div role="tabpanel" id="shared-tabpanel" aria-labelledby={`shared-tab-${active}`} className="space-y-4">
            {active === 'summary' && (
              <>
                <StrictInterviewNotes strict={candidate.strict} />
                {interviewed && (
                  <Assessment
                    title="Interview assessment"
                    score={candidate.interview_score}
                    reviewed={Boolean(candidate.interview_reviewed)}
                    summary={interview.summary}
                    sections={interview.sections}
                    emptyText="No assessment is available for this interview."
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
              </>
            )}

            {active === 'scorecard' && candidate.scorecard && (
              <ScorecardView
                scorecard={candidate.scorecard}
                candidateName={candidate.name}
                role={candidate.record?.role}
                date={candidate.completed_at}
              />
            )}

            {active === 'scores' && (
              <>
                {/* A job with a scoring profile: the weighted table, the total or "incomplete", and
                    the suggested band. */}
                {report && <WeightedScoreCard report={report} />}
                {/* The practical case, scored on its own and never part of the weighted score */}
                {candidate.practical_case && <PracticalCaseCard report={candidate.practical_case} />}
              </>
            )}

            {active === 'conversation' && (
              <>
                <Questions questions={candidate.questions ?? []} />
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
              </>
            )}

            {/* The candidate assessment record, without the company's own panel decision */}
            {active === 'record' && candidate.record && <AssessmentRecordCard record={candidate.record} />}
          </div>
        </div>
      </div>
    </section>
  )
}
