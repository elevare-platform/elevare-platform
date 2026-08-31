// Shared heuristic for "this error message is about a plan/quota limit" —
// used to decide whether to show an inline Upgrade-plan link next to an
// error, regardless of which toast/banner mechanism displays it. One place
// so every surface (jobs, candidate search, talent pool) agrees on when to
// show the CTA instead of each guessing its own pattern.
const PLAN_LIMIT_PATTERN = /plan|limit/i

export function isPlanLimitMessage(message) {
  return typeof message === 'string' && PLAN_LIMIT_PATTERN.test(message)
}
