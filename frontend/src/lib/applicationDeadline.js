// A job stays ACTIVE after its application deadline, but the server turns every application away
// from then on (JOB_DEADLINE_PAST). The screens use this to say so instead of offering a button
// that can only fail. The server stays the judge: this only decides what is shown.
export function applicationsClosed(deadline, now = Date.now()) {
  if (!deadline) return false
  const time = new Date(deadline).getTime()
  return !Number.isNaN(time) && time < now
}
