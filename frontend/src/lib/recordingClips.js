/**
 * The title over one clip. An interview the employer reinstated has one recording per attempt:
 * the first ends where the interview stopped, the next carries on from there.
 */
export function clipTitle(attempt) {
  return attempt > 1 ? `Attempt ${attempt}, after the interview was reinstated` : 'Attempt 1'
}

/**
 * Whether the recordings are to be shown as separate clips: more than one attempt recorded, or
 * the only recording is an earlier attempt's (the latest attempt recorded nothing new).
 * `recordings` is the server's list, oldest first; `videoUrl` the latest attempt's link.
 */
export function showsClips(recordings, videoUrl) {
  const clips = recordings ?? []
  return clips.length > 1 || (clips.length === 1 && !videoUrl)
}
