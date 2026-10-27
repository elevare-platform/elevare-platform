// Helpers for a job's strict-interview question list (docs/08_DECISIONS.md, "The new strict,
// text-only AI interview"). The server applies the same rules and is the authority; these give
// the employer instant feedback and keep the editor's list handling in one tested place.

export const MIN_QUESTION_CHARS = 10
export const MAX_QUESTION_CHARS = 500
export const MIN_SECONDS = 30
export const MAX_SECONDS = 600
export const STEP_SECONDS = 30
export const DEFAULT_SECONDS = 120
// The employer's own follow-up probes for one question: one per line, a few short lines.
export const MAX_PROBES = 6
export const MAX_PROBE_CHARS = 300
// The time to answer a follow-up on one question: 30 seconds to 5 minutes, in steps of 30. When
// the employer sets none the platform's 90 seconds applies (the server's `strict_follow_up_seconds`).
export const MAX_FOLLOW_UP_SECONDS = 300
export const DEFAULT_FOLLOW_UP_SECONDS = 90
// Less than this left of the interview after the answer times, and a follow-up rarely fits.
export const LITTLE_TIME_FOR_FOLLOW_UPS = 180

// What the AI may do after an answer, chosen per job (docs/08_DECISIONS.md, item 40).
export const FOLLOW_UP_MODES = [
  {
    value: 'STANDARD',
    label: 'Follow up when needed',
    help: 'The AI may ask up to two short, neutral follow-ups when an answer is unclear about ownership, scale, results or reasoning. If you write probes for a question, it uses them when one fits.',
  },
  {
    value: 'PROBES_ONLY',
    label: 'Only my probes',
    help: 'The AI may ask only the probes you write under a question, in your words, and never makes one up. A question with no probes gets no follow-up.',
  },
  {
    value: 'NONE',
    label: 'Questions only',
    help: 'The AI asks only the questions above and nothing else, so every candidate gets exactly the same.',
  },
]

/** How much of the interview is left once every question has had its full answer time. */
export function timeLeftForFollowUps(questions, limits) {
  return Math.max(0, limits.max_total_seconds - totalSeconds(questions))
}

/** The probes of one question as separate lines: trimmed, blanks dropped. */
export function probeLines(probes) {
  return String(probes ?? '')
    .split('\n')
    .map((line) => cleanText(line))
    .filter(Boolean)
}

// 30 s, 1 min, 1 min 30 s ... 10 min: the choices for the time to answer one question.
export const TIME_OPTIONS = Array.from(
  { length: (MAX_SECONDS - MIN_SECONDS) / STEP_SECONDS + 1 },
  (_, index) => MIN_SECONDS + index * STEP_SECONDS
)
// The same, up to 5 minutes: the choices for the time to answer a follow-up.
export const FOLLOW_UP_TIME_OPTIONS = TIME_OPTIONS.filter((seconds) => seconds <= 300)

/** 45 as "45 s", 120 as "2 min", 90 as "1 min 30 s". */
export function formatSeconds(seconds) {
  const whole = Math.floor(seconds / 60)
  const rest = seconds % 60
  if (whole === 0) return `${rest} s`
  return rest === 0 ? `${whole} min` : `${whole} min ${rest} s`
}

export function totalSeconds(questions) {
  return questions.reduce((sum, question) => sum + Number(question.time_limit_seconds || 0), 0)
}

/** A question as one tidy line: trimmed, with runs of blanks collapsed (as the server saves it). */
export function cleanText(text) {
  return String(text ?? '').split(/\s+/).filter(Boolean).join(' ')
}

/** A new, empty question for the employer to fill in. `key` is only for the screen's list. */
export function blankQuestion(key) {
  return {
    key,
    text: '',
    time_limit_seconds: DEFAULT_SECONDS,
    source: 'EMPLOYER',
    probes: '',
    follow_up_seconds: null,
    is_practical: false,
  }
}

/** Move the question at `index` one place up (-1) or down (+1). Returns a new list. */
export function moveQuestion(questions, index, direction) {
  const target = index + direction
  if (target < 0 || target >= questions.length) return questions
  const next = [...questions]
  ;[next[index], next[target]] = [next[target], next[index]]
  return next
}

export function removeQuestion(questions, index) {
  return questions.filter((_, position) => position !== index)
}

/**
 * What is wrong with the list, in words the employer can act on. Mirrors the server's rules so
 * the Save button can say why it will not work. `limits` is `{ max_total_seconds }`. There is no
 * limit on how many questions: only the total time (and a question needs at least 30 seconds).
 */
export function problemsWith(questions, limits) {
  const found = []
  if (questions.filter((question) => question.is_practical).length > 1) {
    found.push('Only one question can be the practical case.')
  }
  questions.forEach((question, index) => {
    const probes = probeLines(question.probes)
    if (probes.length > MAX_PROBES) {
      found.push(`Question ${index + 1} has too many probes. Keep it to ${MAX_PROBES}.`)
    }
    if (probes.some((probe) => probe.length > MAX_PROBE_CHARS)) {
      found.push(`A probe on question ${index + 1} is too long. Keep each under ${MAX_PROBE_CHARS} characters.`)
    }
    const length = cleanText(question.text).length
    if (length < MIN_QUESTION_CHARS) {
      found.push(`Question ${index + 1} is too short to be a question.`)
    } else if (length > MAX_QUESTION_CHARS) {
      found.push(`Question ${index + 1} is too long. Keep it under ${MAX_QUESTION_CHARS} characters.`)
    }
  })
  const total = totalSeconds(questions)
  if (total > limits.max_total_seconds) {
    found.push(
      `The answer times add up to ${formatSeconds(total)}, but the whole interview is limited to ${formatSeconds(limits.max_total_seconds)}. Shorten some of the times.`
    )
  }
  return found
}
