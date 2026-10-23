// What the strict interview screen notices and says about leaving it (docs/08_DECISIONS.md, item 25).
// No React and no network here, so each rule can be tested. The numbers that END an interview (4
// leaves, 60 seconds away) belong to the server and arrive with every reply; the wording below uses
// those, so changing them on the server changes what the candidate is told.

// A leave is only reported once it has lasted this long, so a notification or a blip never counts.
export const LEAVE_DELAY_MS = 1000
// The same key pressed again within this time is reported once.
export const KEY_REPEAT_MS = 2000
// How long a warning stays on the screen.
export const WARNING_SHOW_MS = 12000
// How often the screen says it is still there (the server times a reload from this).
export const HEARTBEAT_MS = 15000

/**
 * Why the candidate is away from the interview screen right now, or null when they are not: the
 * page is hidden (another tab or app), the window lost focus, or full screen was exited. All of
 * them at once are ONE leave, so the first that applies is the cause.
 */
export function awayCause(doc = document) {
  if (doc.visibilityState === 'hidden') return 'HIDDEN'
  if (typeof doc.hasFocus === 'function' && !doc.hasFocus()) return 'BLUR'
  if (!doc.fullscreenElement) return 'FULLSCREEN'
  return null
}

const NAMED_KEYS = { Escape: 'Escape', Alt: 'Alt', Meta: 'Meta', OS: 'Meta', F11: 'F11', F12: 'F12' }

/**
 * The name of a key press that tries to leave the interview (Esc, Alt, the Windows or Command key,
 * F11, F12, Ctrl with T, W, N or Tab), or null for any other key. These are recorded and warned
 * about, and never count towards ending the interview.
 */
export function reportableKey(event) {
  if (NAMED_KEYS[event.key]) return NAMED_KEYS[event.key]
  if (event.ctrlKey || event.metaKey) {
    if (event.key === 'Tab') return 'Ctrl+Tab'
    const letter = (event.key || '').toLowerCase()
    if (letter === 't' || letter === 'w' || letter === 'n') return `Ctrl+${letter.toUpperCase()}`
  }
  return null
}

/** The warning to show after a leave, or null when there is none to show (no leave yet, or the
 *  interview has ended, which has its own screen). `state` is what the server last said. */
export function leaveWarning(state) {
  if (!state || state.ended || !state.leaves) return null
  const plural = state.leaves === 1 ? 'time' : 'times'
  return (
    `You have left the interview screen ${state.leaves} ${plural}. `
    + `If you leave it ${state.max_leaves} times, or are away for more than ${state.max_away_seconds} seconds `
    + `in total, the interview ends. You have been away ${state.away_seconds} of ${state.max_away_seconds} seconds.`
  )
}

export const KEY_WARNING = 'That key is noted and shown to the employer. It does not end the interview.'

/** What the screen says once the interview has ended early. `reason` is the server's. */
export function endedMessage(reason) {
  if (reason === 'STOPPED') {
    return {
      title: 'You stopped the interview',
      body: 'The employer has been told. They can let you carry on.',
    }
  }
  return {
    title: 'Your interview has ended',
    body: reason === 'TOO_LONG_AWAY'
      ? 'You were away from the interview screen for too long, so the interview ended.'
      : 'You left the interview screen too many times, so the interview ended.',
  }
}

export const ENDED_FOOTER = (
  'Your answers and your recording up to this point have been sent to the employer. '
  + 'If you think this should not have happened, or you would like to carry on, '
  + 'please contact the employer who invited you.'
)

/** The reason to show for an interview already ended when the page opens, from its status. */
export function reasonFromStatus(status) {
  if (status === 'STOPPED') return 'STOPPED'
  if (status === 'ENDED_CONDUCT') return 'TOO_MANY_LEAVES'
  return null
}
