import { useState } from 'react'
import { Loader2, ShieldCheck } from 'lucide-react'
import api from '@/lib/api'
import { bandForScore } from '@/lib/scoringProfile'
import { RATING_OPTIONS, ratingName } from '@/lib/scorecard'

const MAX_REASON_CHARS = 1000

const formatWhen = (iso) =>
  iso ? new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''

// The total the system's own formula gives for these ratings, or null while one is still unrated.
function totalFor(rows, ratings) {
  if (!rows.length || rows.some((row) => !ratings[row.name])) return null
  return Math.round(rows.reduce((sum, row) => sum + (Number(ratings[row.name]) / 5) * row.weight, 0))
}

/**
 * ScoreReviewPanel - for an Elevare admin only (the server sends `detail.score_review` to no one
 * else). Changes the competency ratings and/or sets the total of a scored interview in place of the
 * system's: the total follows the ratings by the system's own formula unless one is typed, the band
 * follows the total by the job's own cut-offs, and a small "Reviewed" tag shows beside the score for
 * everyone who reads it, the shared link included. The system's own ratings, score and band, and who
 * changed what, stay here. `onChanged` is called after a save or a removal so the window can reload.
 */
export default function ScoreReviewPanel({ jobId, talentPoolProfileId, detail, onChanged }) {
  const review = detail.score_review
  const rows = detail.score_report?.rows ?? []
  const bands = detail.score_report?.bands ?? null
  const original = review.original_ratings ?? {}

  const [ratings, setRatings] = useState(() =>
    Object.fromEntries(rows.map((row) => [row.name, row.rating ?? '']))
  )
  const [startRatings] = useState(ratings)
  // A total typed in, rather than worked out from the ratings, stays as typed while the ratings change.
  const [totalTyped, setTotalTyped] = useState(
    () => detail.reviewed && detail.ai_score != null && detail.ai_score !== totalFor(rows, startRatings)
  )
  const [typedValue, setTypedValue] = useState(detail.ai_score ?? '')
  const [reason, setReason] = useState('')
  const [text, setText] = useState(detail.ai_rationale ?? '')
  // The scorecard as it is printed: the evidence of each competency, the practical case rating, the
  // strengths (one per line) and the human decision wording.
  const card = detail.scorecard ?? null
  const cardRows = card?.rows ?? []
  const [evidence, setEvidence] = useState(() => Object.fromEntries(cardRows.map((row) => [row.name, row.evidence ?? ''])))
  const [startEvidence] = useState(evidence)
  const [practical, setPractical] = useState(card?.practical_rating ?? '')
  const [strengths, setStrengths] = useState((card?.strengths ?? []).join('\n'))
  const [decision, setDecision] = useState(card?.decision ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const computed = totalFor(rows, ratings)
  const shownTotal = totalTyped || !rows.length ? typedValue : (computed ?? '')
  const number = shownTotal === '' ? null : Number(shownTotal)
  const totalValid = number !== null && Number.isInteger(number) && number >= 0 && number <= 100
  const previewBand = totalValid && bands ? bandForScore(number, bands) : null

  const changedRatings = Object.fromEntries(
    rows
      .filter((row) => ratings[row.name] && Number(ratings[row.name]) !== original[row.name])
      .map((row) => [row.name, Number(ratings[row.name])])
  )
  const ratingsMoved = rows.some((row) => String(ratings[row.name]) !== String(startRatings[row.name]))
  const totalMoved = totalValid && number !== detail.ai_score
  // The written assessment: what is shown now, and what the system itself wrote.
  const shownText = detail.ai_rationale ?? ''
  const systemText = review.original_rationale ?? ''
  const textMoved = text.trim() !== shownText.trim()
  // The scorecard fields: what differs from what the system wrote is sent.
  const systemEvidence = review.original_evidence ?? {}
  const systemPractical = detail.practical_case?.complete ? detail.practical_case.score : null
  const systemStrengths = (detail.record?.top_strengths ?? []).join('\n')
  const evidenceSent = Object.fromEntries(
    cardRows
      .filter((row) => (evidence[row.name] ?? '').trim() && evidence[row.name].trim() !== (systemEvidence[row.name] ?? '').trim())
      .map((row) => [row.name, evidence[row.name].trim()])
  )
  const practicalSent = practical !== '' && Number(practical) !== systemPractical ? Number(practical) : null
  const strengthsSent = strengths.trim() && strengths.trim() !== systemStrengths.trim() ? strengths.trim() : null
  const decisionSent = decision.trim() || null
  const scorecardSent =
    Object.keys(evidenceSent).length || practicalSent !== null || strengthsSent || decisionSent
      ? {
          ...(Object.keys(evidenceSent).length ? { evidence: evidenceSent } : {}),
          ...(practicalSent !== null ? { practical_rating: practicalSent } : {}),
          ...(strengthsSent ? { strengths: strengthsSent } : {}),
          ...(decisionSent ? { decision: decisionSent } : {}),
        }
      : null
  const cardMoved =
    cardRows.some((row) => (evidence[row.name] ?? '').trim() !== (startEvidence[row.name] ?? '').trim()) ||
    String(practical) !== String(card?.practical_rating ?? '') ||
    strengths.trim() !== (card?.strengths ?? []).join('\n').trim() ||
    decision.trim() !== (card?.decision ?? '').trim()
  const dirty = ratingsMoved || totalMoved || textMoved || cardMoved
  // What is sent is the whole review: the changed ratings, the total only when it was typed (or an
  // earlier review's typed total is being kept), and the written assessment only when it differs
  // from the system's own.
  const keepTyped = totalTyped || !rows.length
  const sendScore = keepTyped && (totalMoved || detail.reviewed) ? number : null
  const sendRationale = text.trim() && text.trim() !== systemText.trim() ? text.trim() : null
  const hasChange =
    sendScore !== null || Object.keys(changedRatings).length > 0 || sendRationale !== null || scorecardSent !== null
  const canSave = dirty && hasChange && (sendScore === null || totalValid)

  const request = async (call) => {
    if (saving) return
    setSaving(true)
    setError(null)
    try {
      await call()
      setReason('')
      await onChanged?.()
    } catch (err) {
      const message = err?.response?.data?.message
      setError(
        err?.response
          ? (typeof message === 'string' ? message : 'Something went wrong. Please try again.')
          : 'We could not reach the server. Check your connection and try again.'
      )
    } finally {
      setSaving(false)
    }
  }

  const save = (event) => {
    event.preventDefault()
    if (!canSave) return
    request(() =>
      api.put(
        `/api/v1/interviews/${talentPoolProfileId}/score-review`,
        {
          score: sendScore,
          ratings: Object.keys(changedRatings).length ? changedRatings : null,
          rationale: sendRationale,
          ...(scorecardSent ? { scorecard: scorecardSent } : {}),
          reason: reason.trim() || null,
        },
        { params: { job_id: jobId } }
      )
    )
  }

  const remove = () =>
    request(() =>
      api.delete(`/api/v1/interviews/${talentPoolProfileId}/score-review`, { params: { job_id: jobId } })
    )

  return (
    <section aria-label="Review score" className="rounded-xl border border-dashed border-border bg-surface-muted p-4 space-y-3">
      <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted">
        <ShieldCheck size={12} aria-hidden="true" /> Review score (visible to Elevare administrators only)
      </p>
      <p className="text-xs text-text-muted" data-testid="system-score">
        System score: {review.original_score ?? 'none'}
        {review.original_band ? `, ${review.original_band}` : ''}
      </p>

      <form onSubmit={save} className="space-y-3">
        {rows.length > 0 && (
          <table className="w-full text-xs" aria-label="Competency ratings">
            <thead>
              <tr className="border-b border-border text-left text-text-muted">
                <th className="py-1.5 pr-2 font-medium">Competency</th>
                <th className="px-2 py-1.5 text-right font-medium">Weight</th>
                <th className="px-2 py-1.5 text-right font-medium">System</th>
                <th className="pl-2 py-1.5 text-right font-medium">Rating</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.name} className="border-b border-border/60">
                  <td className="py-1.5 pr-2 text-text">{row.name}</td>
                  <td className="px-2 py-1.5 text-right text-text-muted">{row.weight}%</td>
                  <td className="px-2 py-1.5 text-right text-text-muted">{original[row.name] ?? 'Not assessed'}</td>
                  <td className="pl-2 py-1.5 text-right">
                    <select
                      aria-label={`Rating for ${row.name}`}
                      value={ratings[row.name]}
                      onChange={(event) => setRatings((current) => ({ ...current, [row.name]: event.target.value }))}
                      className="rounded-lg border border-border px-1.5 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
                    >
                      {original[row.name] == null && <option value="">Not assessed</option>}
                      {RATING_OPTIONS.map((rating) => (
                        <option key={rating} value={rating}>
                          {rating} {ratingName(rating)}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="review-score" className="block text-[11px] font-medium text-text-muted">
              Total (0 to 100){!totalTyped && rows.length > 0 ? ', worked out from the ratings' : ''}
            </label>
            <input
              id="review-score"
              type="number"
              min="0"
              max="100"
              step="1"
              value={shownTotal}
              onChange={(event) => {
                setTotalTyped(true)
                setTypedValue(event.target.value)
              }}
              className="mt-1 w-24 rounded-lg border border-border px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
            />
          </div>
          {previewBand && (
            <p className="pb-1.5 text-xs text-text" data-testid="band-preview">
              Band: <span className="font-semibold">{previewBand}</span>
            </p>
          )}
          {totalTyped && rows.length > 0 && (
            <button
              type="button"
              onClick={() => setTotalTyped(false)}
              className="pb-1.5 text-xs font-medium text-brand-blue hover:underline"
            >
              Work the total out from the ratings
            </button>
          )}
        </div>

        {card && (
          <fieldset className="space-y-3 rounded-lg border border-border bg-white p-3">
            <legend className="px-1 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
              Scorecard (as printed)
            </legend>
            {cardRows.map((row) => (
              <div key={row.name}>
                <label htmlFor={`evidence-${row.name}`} className="block text-[11px] font-medium text-text-muted">
                  Evidence / Verification: {row.name}
                </label>
                <textarea
                  id={`evidence-${row.name}`}
                  rows={2}
                  maxLength={1000}
                  value={evidence[row.name] ?? ''}
                  onChange={(event) => setEvidence((current) => ({ ...current, [row.name]: event.target.value }))}
                  className="mt-1 w-full rounded-lg border border-border px-2.5 py-1.5 text-xs leading-relaxed focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
                />
              </div>
            ))}
            {card?.show_summary !== false && (
            <>
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label htmlFor="card-practical"className="block text-[11px] font-medium text-text-muted">
                  Practical case rating
                </label>
                <select
                  id="card-practical"
                  value={practical}
                  onChange={(event) => setPractical(event.target.value)}
                  className="mt-1 rounded-lg border border-border px-1.5 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
                >
                  <option value="">None</option>
                  {RATING_OPTIONS.map((rating) => (
                    <option key={rating} value={rating}>
                      {rating} {ratingName(rating)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="min-w-[14rem] flex-1">
                <label htmlFor="card-decision" className="block text-[11px] font-medium text-text-muted">
                  Human decision
                </label>
                <input
                  id="card-decision"
                  type="text"
                  maxLength={300}
                  value={decision}
                  onChange={(event) => setDecision(event.target.value)}
                  placeholder="For example: Proceed to Final Interview / Offer Consideration"
                  className="mt-1 w-full rounded-lg border border-border px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
                />
              </div>
            </div>
            <div>
              <label htmlFor="card-strengths" className="block text-[11px] font-medium text-text-muted">
                Strengths (one per line)
              </label>
              <textarea
                id="card-strengths"
                rows={3}
                maxLength={2000}
                value={strengths}
                onChange={(event) => setStrengths(event.target.value)}
                className="mt-1 w-full rounded-lg border border-border px-2.5 py-1.5 text-xs leading-relaxed focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
              />
            </div>
            </>
            )}
          </fieldset>
        )}

        <div>
          <label htmlFor="review-text" className="block text-[11px] font-medium text-text-muted">
            Written assessment (everyone who reads this interview sees this text)
          </label>
          <textarea
            id="review-text"
            rows={10}
            maxLength={20000}
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="mt-1 w-full rounded-lg border border-border px-2.5 py-1.5 text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
          />
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <p className="text-[11px] text-text-muted">
              Your text replaces the system&apos;s. The system&apos;s own text is kept and can be put back.
            </p>
            {text.trim() !== systemText.trim() && (
              <button
                type="button"
                onClick={() => setText(systemText)}
                className="text-[11px] font-medium text-brand-blue hover:underline"
              >
                Use the system&apos;s text
              </button>
            )}
          </div>
        </div>

        <div>
          <label htmlFor="review-reason" className="block text-[11px] font-medium text-text-muted">
            Reason (optional)
          </label>
          <textarea
            id="review-reason"
            rows={2}
            maxLength={MAX_REASON_CHARS}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            className="mt-1 w-full rounded-lg border border-border px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
          />
        </div>
        {error && (
          <p role="alert" className="text-xs text-red-600">
            {error}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={saving || !canSave}
            className="inline-flex items-center gap-1.5 rounded-lg bg-brand-blue px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
          >
            {saving && <Loader2 size={12} className="animate-spin" aria-hidden="true" />}
            Save score
          </button>
          {detail.reviewed && (
            <button
              type="button"
              onClick={remove}
              disabled={saving}
              className="text-xs font-medium text-brand-blue hover:underline disabled:opacity-50"
            >
              Remove the review (show the system score)
            </button>
          )}
        </div>
      </form>

      {review.reviews.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-text-muted mb-1">History</p>
          <ul className="space-y-1" data-testid="review-history">
            {review.reviews.map((row, index) => {
              const moved = Object.entries(row.ratings ?? {})
              const nothing =
                row.score == null && moved.length === 0 && !row.rationale_changed && !row.scorecard_changed
              return (
                <li key={index} className="text-xs text-text">
                  {nothing ? 'Review removed' : 'Reviewed'}
                  {row.score != null ? `, total set to ${row.score}` : ''}
                  {moved.length > 0 ? `, ratings ${moved.map(([name, rating]) => `${name} ${rating}`).join(', ')}` : ''}
                  {row.rationale_changed ? ', written assessment edited' : ''}
                  {row.scorecard_changed ? ', scorecard filled in' : ''} by{' '}
                  {row.reviewed_by_name}, {formatWhen(row.reviewed_at)}
                  {row.reason ? `. ${row.reason}` : ''}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </section>
  )
}
