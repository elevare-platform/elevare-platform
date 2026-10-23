// How the notes about a strict interview read to the employer and to the client: the sentence for
// each event on the timeline, why it ended, and the fixed note that they are not proof
// (docs/08_DECISIONS.md, item 25 (h); docs/14_AI_INTERVIEW_RULES.md, section 3).

export const STRICT_NOTE = (
  'These notes are for you to review. They are not proof of anything, and no decision has been made for you.'
)

/** Why an interview ended early, as a sentence about the candidate. */
export function endedText(reason) {
  switch (reason) {
    case 'TOO_MANY_LEAVES':
      return 'The candidate left the interview screen too many times, so the interview ended.'
    case 'TOO_LONG_AWAY':
      return 'The candidate was away from the interview screen for too long, so the interview ended.'
    case 'STOPPED':
      return 'The candidate chose to stop the interview. This was their own choice.'
    default:
      return null
  }
}

const ENDED_SHORT = {
  TOO_MANY_LEAVES: 'they left the interview screen too many times',
  TOO_LONG_AWAY: 'they were away from the interview screen for too long',
  STOPPED: 'they chose to stop',
}

const LEAVE_CAUSES = {
  HIDDEN: 'switched to another tab or app',
  BLUR: 'the window lost focus',
  FULLSCREEN: 'left full screen',
}

const KEY_NAMES = {
  Escape: 'Esc',
  Meta: 'the Windows or Command key',
}

/** The sentence for one row of the timeline. */
export function describeEvent(event) {
  const seconds = event.duration_seconds
  switch (event.kind) {
    case 'LEFT_PAGE': {
      const cause = LEAVE_CAUSES[event.detail] ? ` (${LEAVE_CAUSES[event.detail]})` : ''
      const length = seconds == null ? ', and was still away when the interview ended' : ` for ${seconds} s`
      return `Left the interview screen${cause}${length}`
    }
    case 'RELOAD':
      return `Reloaded the page, or came back after closing it${seconds == null ? '' : `, away about ${seconds} s`}`
    case 'KEY_PRESS':
      return `Pressed ${KEY_NAMES[event.detail] ?? event.detail ?? 'a key'}`
    case 'STOPPED':
      return 'Stopped the interview (their own choice)'
    case 'ENDED':
      return `The interview ended because ${ENDED_SHORT[event.detail] ?? 'of how it went'}`
    case 'REINSTATED':
      return 'The interview was reinstated so the candidate could carry on'
    default:
      return event.kind
  }
}

/** A date and time as the reader's own browser writes them, or a dash. */
export function formatWhen(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

/** "Question 2" for a question, "Follow-up to question 2" for a follow-up. */
export function turnTitle(turn) {
  return turn.kind === 'FOLLOW_UP' ? `Follow-up to question ${turn.number}` : `Question ${turn.number}`
}

/** What an employer sees for an interview status that has ended early, or null. */
export function endedBadge(status) {
  if (status === 'STOPPED') return 'Stopped by the candidate'
  if (status === 'ENDED_CONDUCT') return 'Ended early'
  return null
}

export const isEndedStatus = (status) => status === 'ENDED_CONDUCT' || status === 'STOPPED'
