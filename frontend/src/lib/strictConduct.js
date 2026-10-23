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
// Nothing counts as a leave until the screen has been calm (visible, in focus, full screen) for
// CALM_MS in a row after the interview starts (full screen taking effect, a browser pop-up), or
// SETTLE_MS has passed, whichever is first.
export const CALM_MS = 1500
export const SETTLE_MS = 15000
// The tab's title while the candidate is away, so they see it in the tab list and the taskbar.
export const AWAY_TITLE = 'Return to your interview'

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

const MODIFIER_KEYS = new Set(['Control', 'Shift', 'Alt', 'Meta', 'OS', 'AltGraph'])
const SPECIAL_KEYS = {
  ' ': 'Space',
  Tab: 'Tab',
  Enter: 'Enter',
  Backspace: 'Backspace',
  Delete: 'Delete',
  Insert: 'Insert',
  Home: 'Home',
  End: 'End',
  PageUp: 'PageUp',
  PageDown: 'PageDown',
  ArrowUp: 'Up',
  ArrowDown: 'Down',
  ArrowLeft: 'Left',
  ArrowRight: 'Right',
  Escape: 'Escape',
}

/** The name of the key in a shortcut: a letter or digit as a capital, a known key by its name, any
 *  other (punctuation, a symbol) as "Other". */
function keyName(key) {
  if (SPECIAL_KEYS[key]) return SPECIAL_KEYS[key]
  if (/^F([1-9]|1[0-2])$/.test(key)) return key
  if (/^[A-Za-z0-9]$/.test(key)) return key.toUpperCase()
  return 'Other'
}

/**
 * The name of a key press the employer is told about, or null for an ordinary key. These are
 * recorded and warned about, and never count towards ending the interview:
 *   - any shortcut, written as the FULL combination in a fixed order, such as Ctrl+T, Alt+Tab,
 *     Ctrl+Shift+I or Meta+L (a key pressed with Ctrl, Alt or the Windows or Command key);
 *   - Esc, and the function keys F1 to F12;
 *   - the Alt key, or the Windows or Command key, pressed by itself.
 * A lone Ctrl or Shift is ordinary and is not reported.
 */
export function reportableKey(event) {
  const key = event.key || ''
  if (MODIFIER_KEYS.has(key)) {
    if (key === 'Alt') return 'Alt'
    if (key === 'Meta' || key === 'OS') return 'Meta'
    return null
  }
  if (event.ctrlKey || event.altKey || event.metaKey) {
    const parts = []
    if (event.ctrlKey) parts.push('Ctrl')
    if (event.altKey) parts.push('Alt')
    if (event.shiftKey) parts.push('Shift')
    if (event.metaKey) parts.push('Meta')
    return [...parts, keyName(key)].join('+')
  }
  if (key === 'Escape') return 'Escape'
  if (/^F([1-9]|1[0-2])$/.test(key)) return key
  return null
}

/**
 * What the box that dims the screen says when the candidate comes back from leaving it, from what
 * the server counted (`state`), or null when there is nothing to say (no leave counted, or the
 * interview has ended, which has its own screen). It says how many warnings are used, what one
 * more leave costs, and that the time is still running.
 */
export function leaveNotice(state) {
  if (!state || state.ended || !state.leaves) return null
  const allowed = state.max_leaves - 1
  const used = Math.min(state.leaves, allowed)
  const leavesLeft = Math.max(0, state.max_leaves - state.leaves)
  const secondsLeft = Math.max(0, state.max_away_seconds - state.away_seconds)
  const last = leavesLeft <= 1
  const more = leavesLeft === 1 ? '1 more time' : `${leavesLeft} more times`
  return {
    used,
    allowed,
    last,
    // The time away used out of the total that ends the interview, for the bar in the box.
    away: { used: Math.min(state.away_seconds, state.max_away_seconds), max: state.max_away_seconds },
    lines: [
      last
        ? `This was your last warning. If you leave the screen again, or are away for more than ${secondsLeft} more seconds in total, the interview ends.`
        : `If you leave it ${more}, or are away for more than ${secondsLeft} more seconds in total, the interview ends.`,
      'The time for your question is still running.',
    ],
  }
}

/**
 * How the "time away" line looks: calm at first, amber from half the allowance, bold red from
 * four fifths of it. `state` is the server's conduct state.
 */
export function awayTone({ away_seconds: used, max_away_seconds: max }) {
  if (used >= max * 0.8) return 'font-semibold text-red-600'
  if (used >= max * 0.5) return 'font-medium text-amber-700'
  return 'text-text-muted'
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
