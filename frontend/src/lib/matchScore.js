// Turns a raw 0-100 match/similarity score into a Strong/Good/Fair band.
//
// The raw number comes straight out of an AI embedding comparison (cosine
// similarity), which behaves nothing like a percentage grade: two genuinely
// well-matched texts (e.g. a CV and a job post) rarely score above 70-80%
// even at their best, because they're different kinds of writing, not
// paraphrases of each other. Showing that raw number as "66%" reads like a
// D grade to anyone unfamiliar with how embeddings work, even when it's
// actually one of the strongest matches available.
//
// One universal scale — Applications, Talent Pool, AI Talent Match, and
// Candidate Search all compute scores the same way now (embedding cosine
// similarity, modulated by skill overlap; see EmbeddingAIService in the
// backend), so they land in the same real-world range. Thresholds are
// grounded in the real score distribution observed in the database, not
// guessed. There used to be a separate, lower threshold set for
// Applications, back when its match_score formula was structurally weaker
// (plain keyword matching, capped near 50) than the other three surfaces —
// that's fixed now, so one scale is correct everywhere.
const THRESHOLDS = { strong: 65, good: 40 }

const BANDS = {
  strong: { label: 'Strong match', className: 'bg-green-100 text-green-700 border-green-200' },
  good: { label: 'Good match', className: 'bg-amber-100 text-amber-700 border-amber-200' },
  fair: { label: 'Fair match', className: 'bg-gray-100 text-gray-600 border-gray-200' },
  unscored: { label: 'Not yet scored', className: 'bg-gray-100 text-gray-400 border-gray-200' },
}

// Why a candidate has no score (`ai_score_failure` on a talent pool profile or an
// application). Shown instead of "Not yet scored", which would read as "wait a moment".
// A failure is never a low score, and it never replaces a real one.
const FAILURE_BANDS = {
  CV_UNREADABLE: {
    key: 'unreadable',
    label: 'Could not read CV',
    className: 'bg-red-50 text-red-600 border-red-200',
    help:
      'Nothing could be read from this CV, so it was not scored. A clearer file, such as a text PDF instead of a photo or a scan, usually fixes it.',
  },
  SCORING_FAILED: {
    key: 'failed',
    label: 'Scoring unavailable',
    className: 'bg-orange-50 text-orange-700 border-orange-200',
    help: 'Scoring did not complete, so there is no score. This is not a low score.',
  },
}

/** The sentence that explains a failure, or null when there is none. */
export function scoreFailureHelp(failure) {
  return FAILURE_BANDS[failure]?.help ?? null
}

export function matchScoreBand(score, failure = null) {
  if (score === null || score === undefined) {
    const { help, ...band } = FAILURE_BANDS[failure] ?? {}
    return help ? band : { key: 'unscored', ...BANDS.unscored }
  }
  if (score >= THRESHOLDS.strong) return { key: 'strong', ...BANDS.strong }
  if (score >= THRESHOLDS.good) return { key: 'good', ...BANDS.good }
  return { key: 'fair', ...BANDS.fair }
}
