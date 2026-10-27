import { ClipboardList } from 'lucide-react'

/**
 * PracticalCaseCard - the practical case of an interview: a scenario the candidate worked through
 * aloud, scored on five criteria and reported on its own out of 5. It is never part of the weighted
 * score (docs/08_DECISIONS.md, item 43). When a criterion could not be rated the case is
 * INCOMPLETE and gives no number. `report` is the server's practical case report.
 */
export default function PracticalCaseCard({ report }) {
  const { complete, score, rows, unassessed = [], summary } = report
  const rated = rows.length - unassessed.length

  return (
    <div className="rounded-xl border border-border p-4 space-y-3" data-testid="practical-case">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted">
          <ClipboardList size={12} aria-hidden="true" /> Practical case
        </p>
        {complete ? (
          <span className="rounded-full bg-brand-blue/10 px-2.5 py-0.5 text-xs font-bold text-brand-blue" data-testid="practical-score">
            {score.toFixed(1)} / 5
          </span>
        ) : (
          <span className="rounded-full border border-amber-200 bg-amber-100 px-2.5 py-0.5 text-xs font-bold text-amber-800" data-testid="practical-incomplete">
            Incomplete
          </span>
        )}
      </div>

      <p className="text-xs text-text-muted">
        A scenario the candidate worked through aloud, scored on its own. It is not part of the weighted score.
      </p>

      {!complete && (
        <p role="note" className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {rated} of {rows.length} criteria could be rated (not covered: {unassessed.join(', ')}). No case score
          is given. A person decides whether more evidence is needed.
        </p>
      )}

      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border text-left text-text-muted">
            <th className="py-1.5 pr-2 font-medium">Criterion</th>
            <th className="px-2 py-1.5 text-right font-medium">Weight</th>
            <th className="pl-2 py-1.5 text-right font-medium">Rating</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className="border-b border-border/60 align-top">
              <td className="py-1.5 pr-2 text-text">
                {row.name}
                {row.rationale && <span className="block text-text-muted">{row.rationale}</span>}
              </td>
              <td className="px-2 py-1.5 text-right text-text-muted">{row.weight}%</td>
              <td className="pl-2 py-1.5 text-right text-text">
                {row.rating == null ? <span className="text-amber-700">Not covered</span> : `${row.rating} of 5`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {summary && <p className="text-sm leading-relaxed text-text">{summary}</p>}
    </div>
  )
}
