// Why the platform switched a job off (`disabled_reason` on the job), in a sentence the employer
// can act on. A switched-off job keeps its applicants and can be re-published once the plan
// allows it.
const REASONS = {
  APPLICANT_LIMIT: 'it reached the most applicants your plan allows',
  EXPIRED: 'your plan runs a job for 30 days',
  PLAN_LAPSED: 'your plan has ended',
}

export function disabledNote(job) {
  const why = REASONS[job.disabled_reason]
  return `Switched off${why ? `: ${why}` : ''}. Your applicants are kept. Upgrade your plan to re-publish it.`
}
