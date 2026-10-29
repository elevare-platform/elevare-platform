import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Printer } from 'lucide-react'
import { evaluationDate, pointsText, ratingText } from '@/lib/scorecard'

/**
 * ScorecardSheet - the interview scorecard laid out as Elevare's printed scorecard: the heading, a
 * table of Competency, Weight, Rating /5, Weighted Points and Evidence / Verification, the total
 * as points out of 50 with the 100-point total beside it, then the practical case rating, the
 * strengths and the human decision. With the job's scores switched off (`scorecard.hidden`) there
 * are no points, totals or practical rating: the ratings, the evidence, the strengths and the
 * decision stay.
 */
function ScorecardSheet({ scorecard, candidateName, role, date }) {
  const { rows, hidden } = scorecard

  return (
    <div className="space-y-4 text-text" data-testid="scorecard-sheet">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wide">Elevare Human Solutions</p>
        <h3 className="mt-1 text-lg font-semibold">Interview Scorecard{role ? `: ${role}` : ''}</h3>
        <p className="mt-2 text-xs">
          <span className="font-semibold">Candidate Name:</span> {candidateName}
        </p>
        {date && (
          <p className="text-xs">
            <span className="font-semibold">Date of Evaluation:</span> {evaluationDate(date)}
          </p>
        )}
      </div>

      <div>
        <p className="mb-1 text-xs font-bold uppercase tracking-wide text-text-muted">Role scorecard</p>
        <table className="w-full border-collapse text-xs" data-testid="scorecard-table">
          <thead>
            <tr>
              <th className="border border-border px-2 py-1.5 text-left font-semibold">Competency</th>
              <th className="border border-border px-2 py-1.5 text-left font-semibold">Weight</th>
              <th className="border border-border px-2 py-1.5 text-left font-semibold">Rating /5</th>
              {!hidden && <th className="border border-border px-2 py-1.5 text-left font-semibold">Weighted Points</th>}
              <th className="border border-border px-2 py-1.5 text-left font-semibold">Evidence / Verification</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.name} className="align-top">
                <td className="border border-border px-2 py-1.5 font-semibold">{row.name}</td>
                <td className="border border-border px-2 py-1.5">{row.weight}%</td>
                <td className="border border-border px-2 py-1.5">{ratingText(row.rating)}</td>
                {!hidden && (
                  <td className="border border-border px-2 py-1.5">{row.points == null ? '' : pointsText(row.points)}</td>
                )}
                <td className="border border-border px-2 py-1.5">{row.evidence}</td>
              </tr>
            ))}
            {!hidden && (
              <tr data-testid="scorecard-total">
                <td className="border border-border px-2 py-1.5 font-semibold">Total</td>
                <td className="border border-border px-2 py-1.5 font-semibold">
                  {rows.reduce((sum, row) => sum + row.weight, 0)}%
                </td>
                <td className="border border-border px-2 py-1.5" />
                <td className="border border-border px-2 py-1.5 font-semibold">
                  {scorecard.total_points == null
                    ? ''
                    : `${pointsText(scorecard.total_points)} / ${pointsText(scorecard.max_points).replace(/\.0$/, '')}${
                        scorecard.total_score == null ? '' : ` (${scorecard.total_score}/100)`
                      }`}
                </td>
                <td className="border border-border px-2 py-1.5" />
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {scorecard.show_summary !== false && (
      <div className="space-y-1.5 text-xs">
        <p className="text-sm font-semibold">Evaluation Summary</p>
        {!hidden && scorecard.practical_rating != null && (
          <p data-testid="scorecard-practical">
            <span className="font-semibold">Practical Case Rating:</span> {Number(scorecard.practical_rating).toFixed(1)} / 5
          </p>
        )}
        {scorecard.strengths.length > 0 && (
          <div data-testid="scorecard-strengths">
            <p className="font-semibold">Strengths:</p>
            <ul className="list-disc space-y-0.5 pl-5">
              {scorecard.strengths.map((line, index) => (
                <li key={index}>{line}</li>
              ))}
            </ul>
          </div>
        )}
        {(scorecard.decision || scorecard.panel_decision) && (
          <p data-testid="scorecard-decision">
            <span className="font-semibold">Human Decision:</span> {scorecard.decision ?? ''}
            {scorecard.decision && scorecard.panel_decision ? ' ' : ''}
            {scorecard.panel_decision && (
              <span className="text-text-muted">
                {scorecard.decision ? `(panel: ${scorecard.panel_decision})` : scorecard.panel_decision}
              </span>
            )}
          </p>
        )}
      </div>
      )}
    </div>
  )
}

/**
 * ScorecardView - the scorecard on screen, with a button that prints it (the browser's print
 * dialog, which can save a PDF). The printed copy is the same sheet rendered at the end of the page,
 * so no window or scrolling box clips it; `candidateName`, `role` and `date` fill its heading.
 */
export default function ScorecardView({ scorecard, candidateName, role, date }) {
  // The printed copy exists only while printing: it is copied to the end of the page, the print
  // dialog opens, and it goes away when the dialog closes.
  const [printing, setPrinting] = useState(false)

  useEffect(() => {
    if (!printing) return undefined
    const done = () => setPrinting(false)
    document.body.classList.add('printing-scorecard')
    window.addEventListener('afterprint', done)
    window.print()
    return () => {
      document.body.classList.remove('printing-scorecard')
      window.removeEventListener('afterprint', done)
    }
  }, [printing])

  if (!scorecard) return null
  const sheet = <ScorecardSheet scorecard={scorecard} candidateName={candidateName} role={role} date={date} />

  return (
    <section aria-label="Scorecard" className="rounded-xl border border-border bg-white p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Scorecard</p>
        <button
          type="button"
          onClick={() => setPrinting(true)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-xs font-semibold text-text hover:bg-surface-muted"
        >
          <Printer size={12} aria-hidden="true" /> Download PDF
        </button>
      </div>
      {sheet}
      {printing && createPortal(<div className="scorecard-print-root" data-testid="scorecard-print">{sheet}</div>, document.body)}
    </section>
  )
}
