import { AlertCircle, ClipboardList, ScrollText } from 'lucide-react'
import { STRICT_NOTE, describeEvent, endedText, formatWhen, turnTitle } from '@/lib/strictNotes'

function Fact({ label, value }) {
  return (
    <div className="rounded-lg border border-border bg-white px-3 py-2 text-center">
      <p className="text-lg font-bold text-text tabular-nums">{value}</p>
      <p className="text-[11px] text-text-muted">{label}</p>
    </div>
  )
}

/**
 * RecordingNotice - what to say about a strict interview's recording when the video is not there,
 * or is not all of it. An interview that took more than one sitting has its pieces joined after it
 * finishes, so for a short while there is no video yet; the server then sends no link and sets
 * `recording_pending`. If the joining never finishes it sets `recording_partial` instead, and
 * the video that is shown covers only part of the interview. Renders nothing when neither applies.
 */
export function RecordingNotice({ strict }) {
  if (strict?.recording_pending) {
    return (
      <p role="status" className="rounded-lg border border-dashed border-border py-6 text-center text-xs text-text-muted">
        The recording is being put together from the parts of this interview. Check back in a minute.
      </p>
    )
  }
  if (strict?.recording_partial) {
    return (
      <p role="note" className="rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-900">
        The recording could not be put together, so the video may show only part of this interview.
        The notes and answers below are complete.
      </p>
    )
  }
  return null
}

/**
 * StrictInterviewNotes - what the employer, and the client on the shared link, are shown about a
 * strict interview next to the recording: the rules the candidate accepted (version, date and
 * time), how it ended if it ended early, a conduct summary, the timeline, and each answer under
 * its question. The notes are for a person to review: they are never proof, nothing is decided
 * from them automatically, and this says so.
 *
 * `strict` is the server's StrictDetail. The counts are for the latest attempt (an interview the
 * employer reinstated starts its warnings again); the timeline shows every attempt.
 */
export default function StrictInterviewNotes({ strict }) {
  if (!strict) return null
  const ended = endedText(strict.ended)

  return (
    <section aria-label="Interview notes" className="space-y-3 rounded-xl border border-border bg-surface-muted p-4">
      <div>
        <h3 className="flex items-center gap-1.5 text-sm font-semibold text-text">
          <ClipboardList size={14} aria-hidden="true" /> Interview notes
        </h3>
        <p className="mt-0.5 text-xs text-text-muted">{STRICT_NOTE}</p>
      </div>

      {ended && (
        <p role="note" className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-900">
          <AlertCircle size={14} className="mt-0.5 flex-shrink-0 text-amber-600" aria-hidden="true" />
          <span>{ended}</span>
        </p>
      )}

      <p className="text-xs text-text-muted">
        <span className="font-medium text-text">Rules accepted:</span>{' '}
        {strict.rules_version
          ? `version ${strict.rules_version}, on ${formatWhen(strict.rules_accepted_at)}`
          : 'not recorded'}
        {strict.attempt > 1 && <> · This is attempt {strict.attempt}.</>}
      </p>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Fact label="Times they left the screen" value={strict.leaves} />
        <Fact label="Seconds away in total" value={strict.away_seconds} />
        <Fact label="Reloads" value={strict.reloads} />
        <Fact label="Keys noted" value={strict.key_presses} />
      </div>
      {strict.attempt > 1 && (
        <p className="text-[11px] text-text-muted">These counts are for the latest attempt. The timeline shows every attempt.</p>
      )}

      <div>
        <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted">Timeline</h4>
        {strict.events.length === 0 ? (
          <p className="text-xs text-text-muted">Nothing was noted: the candidate stayed on the screen.</p>
        ) : (
          <ol className="max-h-48 space-y-1 overflow-y-auto rounded-lg border border-border bg-white p-2 text-xs">
            {strict.events.map((event, index) => (
              <li key={index} className="flex gap-2">
                <span className="flex-shrink-0 tabular-nums text-text-muted">{formatWhen(event.occurred_at)}</span>
                <span className="text-text">
                  {strict.attempt > 1 && <span className="mr-1 text-text-muted">[attempt {event.attempt}]</span>}
                  {describeEvent(event)}
                </span>
              </li>
            ))}
          </ol>
        )}
        <p className="mt-1 text-[11px] text-text-muted">
          Times are when the server heard of each event. Use them to look at the same moment in the recording.
        </p>
      </div>

      {strict.turns.length > 0 && (
        <div>
          <h4 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted">
            <ScrollText size={12} aria-hidden="true" /> Questions and answers
          </h4>
          <ol className="space-y-2">
            {strict.turns.map((turn, index) => (
              <li key={index} className="rounded-lg border border-border bg-white p-2.5">
                <p className="text-[11px] font-semibold text-brand-blue">{turnTitle(turn)}</p>
                <p className="mt-0.5 text-xs font-medium text-text">{turn.question}</p>
                <p className="mt-1 whitespace-pre-wrap text-xs text-text-muted">
                  {turn.answer ?? (turn.answered ? 'No answer could be written down. Please check the recording.' : 'Not answered.')}
                </p>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  )
}
