// Helpers for the interview scorecard, laid out as Elevare's printed scorecard.

export const RATING_NAMES = { 1: 'Insufficient evidence', 2: 'Limited', 3: 'Competent', 4: 'Strong', 5: 'Exceptional' }

// Ratings go from 1 to 5 in steps of a half (3.5).
export const RATING_OPTIONS = [1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]

/** What a rating is called; a half point sits between two levels ('Competent to Strong'). */
export function ratingName(rating) {
  const whole = Math.floor(rating)
  return Number.isInteger(rating) ? RATING_NAMES[whole] : `${RATING_NAMES[whole]} to ${RATING_NAMES[whole + 1]}`
}

/** A rating as the printed scorecard writes it: one decimal (4.0, 3.5). */
export const ratingText = (rating) => (rating == null ? 'Not assessed' : Number(rating).toFixed(1))

/** Weighted points as the printed scorecard writes them: 12.0, 5.25, 1.5. */
export function pointsText(points) {
  const text = String(Number(Number(points).toFixed(2)))
  return text.includes('.') ? text : `${text}.0`
}

/** The date of evaluation as the printed scorecard writes it: October 28, 2026. */
export function evaluationDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
}
