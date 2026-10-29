import { Scale } from 'lucide-react'
import { cn } from '@/lib/utils'
import { BAND_NAMES, BAND_STYLE } from '@/lib/scoringProfile'
import ReviewedTag from '@/components/employer/ReviewedTag'

const points = (value) => (Number.isInteger(value) ? String(value) : value.toFixed(1))

/**
 * WeightedScoreCard - the weighted score of an interview scored with a job's scoring profile: the
 * competencies with their weights, ratings and points, the total and the suggested band, or, when
 * a competency could not be assessed, an INCOMPLETE score with no number and no band, for a
 * person to decide on. `report` is the server's score report; `children` is the written
 * assessment shown under the table.
 */
export default function WeightedScoreCard({ report, title = 'Interview Assessment', children }) {
  const { complete, score, band, rows, key_flags: keyFlags = [], unassessed = [] } = report
  // The job's score number switch is off: the band and the ratings are shown, but no total and no
  // points, nor the counts of points in the incomplete notice.
  const numberHidden = Boolean(report.number_hidden)

  // The job's switch has the total and the band left out: only the competencies and their ratings.
  if (report.hidden) {
    return (
      <div className="rounded-xl border border-border p-4 space-y-3" data-testid="weighted-score">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted">
          <Scale size={12} aria-hidden="true" /> {title}
        </p>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border text-left text-text-muted">
              <th className="py-1.5 pr-2 font-medium">Competency</th>
              <th className="px-2 py-1.5 text-right font-medium">Weight</th>
              <th className="pl-2 py-1.5 text-right font-medium">Rating</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.name} className="border-b border-border/60 align-top">
                <td className="py-1.5 pr-2 text-text">
                  {row.name}
                  {row.key && (
                    <span className="ml-1.5 rounded-full bg-brand-blue/10 px-1.5 py-0.5 text-[10px] font-semibold text-brand-blue">Key</span>
                  )}
                </td>
                <td className="px-2 py-1.5 text-right text-text-muted">{row.weight}%</td>
                <td className="pl-2 py-1.5 text-right text-text">
                  {row.rating == null ? <span className="text-amber-700">Not assessed</span> : `${row.rating} of 5`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {children}
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-border p-4 space-y-3" data-testid="weighted-score">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted">
          <Scale size={12} aria-hidden="true" /> {title}
        </p>
        {complete ? (
          <span className="inline-flex items-center gap-1.5">
            {report.reviewed && <ReviewedTag />}
            {!numberHidden && (
              <span className="rounded-full bg-brand-blue/10 px-2.5 py-0.5 text-xs font-bold text-brand-blue" data-testid="weighted-total">
                {score} / 100
              </span>
            )}
          </span>
        ) : (
          <span className="rounded-full border border-amber-200 bg-amber-100 px-2.5 py-0.5 text-xs font-bold text-amber-800" data-testid="weighted-incomplete">
            Incomplete score
          </span>
        )}
      </div>

      {complete ? (
        <div className="space-y-1">
          <p className="text-xs text-text-muted">Suggested band (provisional)</p>
          <span
            data-testid="weighted-band"
            className={cn('inline-block rounded-full border px-3 py-1 text-sm font-semibold', BAND_STYLE[band] ?? BAND_STYLE[BAND_NAMES.hold])}
          >
            {band}
          </span>
        </div>
      ) : (
        <p role="note" className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {numberHidden
            ? `Not every competency could be assessed (not assessed: ${unassessed.join(', ')}). No band is given. A person decides whether more evidence is needed.`
            : `${points(report.points)} of ${report.assessed_weight} weighted points could be assessed (not assessed: ${unassessed.join(', ')}). No full score and no band are given. A person decides whether more evidence is needed.`}
        </p>
      )}

      {keyFlags.length > 0 && (
        <p role="note" data-testid="key-flags" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
          Key competency rated under {report.key_min_rating} of 5: {keyFlags.join(', ')}.
          {complete && !report.reviewed ? ' The band is held at Hold for evidence until a person has looked at it.' : ''}
        </p>
      )}

      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border text-left text-text-muted">
            <th className="py-1.5 pr-2 font-medium">Competency</th>
            <th className="px-2 py-1.5 text-right font-medium">Weight</th>
            <th className="px-2 py-1.5 text-right font-medium">Rating</th>
            {!numberHidden && <th className="pl-2 py-1.5 text-right font-medium">Points</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name} className="border-b border-border/60 align-top">
              <td className="py-1.5 pr-2 text-text">
                {row.name}
                {row.key && (
                  <span className="ml-1.5 rounded-full bg-brand-blue/10 px-1.5 py-0.5 text-[10px] font-semibold text-brand-blue">Key</span>
                )}
              </td>
              <td className="px-2 py-1.5 text-right text-text-muted">{row.weight}%</td>
              <td className="px-2 py-1.5 text-right text-text">
                {row.rating == null ? <span className="text-amber-700">Not assessed</span> : `${row.rating} of 5`}
              </td>
              {!numberHidden && (
                <td className="pl-2 py-1.5 text-right text-text">
                  {row.rating == null ? '–' : points((row.rating / 5) * row.weight)}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      <p className="text-[11px] text-text-muted">
        {numberHidden
          ? 'The band is a label from proposed thresholds, for a panel to read; a person makes every decision.'
          : 'Points are the rating out of 5 times the weight. The band is a label on the total from proposed thresholds, for a panel to read; a person makes every decision.'}
      </p>

      {children}
    </div>
  )
}
