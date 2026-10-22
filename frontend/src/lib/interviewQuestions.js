// Helpers for a job's strict-interview question list (docs/08_DECISIONS.md, "The new strict,
// text-only AI interview"). The server applies the same rules and is the authority; these give
// the employer instant feedback and keep the editor's list handling in one tested place.

export const MIN_QUESTION_CHARS = 10
export const MAX_QUESTION_CHARS = 500
export const MIN_SECONDS = 30
export const MAX_SECONDS = 600
export const STEP_SECONDS = 30
export const DEFAULT_SECONDS = 120

// 30 s, 1 min, 1 min 30 s ... 10 min: the choices for the time to answer one question.
export const TIME_OPTIONS = Array.from(
  { length: (MAX_SECONDS - MIN_SECONDS) / STEP_SECONDS + 1 },
  (_, index) => MIN_SECONDS + index * STEP_SECONDS
)

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
  return { key, text: '', time_limit_seconds: DEFAULT_SECONDS, source: 'EMPLOYER' }
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
 * the Save button can say why it will not work. `limits` is `{ max_questions, max_total_seconds }`.
 */
export function problemsWith(questions, limits) {
  const found = []
  if (questions.length > limits.max_questions) {
    found.push(`An interview can have at most ${limits.max_questions} questions.`)
  }
  questions.forEach((question, index) => {
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
