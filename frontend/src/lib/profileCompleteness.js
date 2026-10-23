// What a candidate profile still needs before it counts as complete. The server decides
// (`compute_profile_completion`, backend/app/modules/candidates/repository.py): the four fields
// below must be filled and there must be at least one CV. This mirrors that rule only so the
// screen can SAY what is missing, instead of guessing "a CV" every time.

const REQUIRED_FIELDS = [
  { field: 'bio', label: 'about you' },
  { field: 'skills', label: 'skills' },
  { field: 'years_of_experience', label: 'years of experience' },
  { field: 'location', label: 'location' },
]

export const CV_MISSING = 'a CV'

function isFilled(value) {
  if (Array.isArray(value)) return value.length > 0
  return value !== '' && value !== null && value !== undefined
}

/** The labels of what is still missing, in the order the form shows them, with "a CV" last. */
export function missingForCompletion(values, cvCount) {
  const missing = REQUIRED_FIELDS.filter(({ field }) => !isFilled(values?.[field])).map(({ label }) => label)
  if (!cvCount) missing.push(CV_MISSING)
  return missing
}

/** "a", "a and b", "a, b and c". */
export function joinList(items) {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} and ${items.at(-1)}`
}
