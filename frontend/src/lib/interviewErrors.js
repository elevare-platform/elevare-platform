// The AI interview off switch answers new invites and new sessions with a 503
// and the code AI_INTERVIEWS_DISABLED. Return its message so screens can show
// it instead of a generic failure; null for any other error.
export function interviewUnavailableMessage(err) {
  const data = err?.response?.data
  return data?.code === 'AI_INTERVIEWS_DISABLED' ? data.message : null
}
