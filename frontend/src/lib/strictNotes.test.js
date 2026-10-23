import { describe, it, expect } from 'vitest'
import {
  STRICT_NOTE,
  describeEvent,
  endedBadge,
  endedText,
  formatWhen,
  isEndedStatus,
  turnTitle,
} from './strictNotes'

describe('endedText', () => {
  it.each(['TOO_MANY_LEAVES', 'TOO_LONG_AWAY', 'STOPPED'])('has a sentence for %s', (reason) => {
    expect(endedText(reason)).toMatch(/^The candidate /)
  })

  it('says a stop was the candidates own choice', () => {
    expect(endedText('STOPPED')).toContain('their own choice')
  })

  it('has nothing for an interview that did not end early', () => {
    expect(endedText(null)).toBeNull()
    expect(endedText(undefined)).toBeNull()
  })
})

describe('describeEvent', () => {
  it('says how long a leave lasted and why', () => {
    expect(describeEvent({ kind: 'LEFT_PAGE', detail: 'HIDDEN', duration_seconds: 12 })).toBe(
      'Left the interview screen (switched to another tab or app) for 12 s'
    )
    expect(describeEvent({ kind: 'LEFT_PAGE', detail: 'FULLSCREEN', duration_seconds: 3 })).toContain('left full screen')
    expect(describeEvent({ kind: 'LEFT_PAGE', detail: 'BLUR', duration_seconds: 3 })).toContain('lost focus')
  })

  it('says so when a leave was still open when the interview ended', () => {
    expect(describeEvent({ kind: 'LEFT_PAGE', detail: 'HIDDEN', duration_seconds: null })).toContain(
      'still away when the interview ended'
    )
  })

  it('describes a reload with the time away', () => {
    expect(describeEvent({ kind: 'RELOAD', duration_seconds: 20 })).toBe(
      'Reloaded the page, or came back after closing it, away about 20 s'
    )
  })

  it('names the key, in words for the keys that need them', () => {
    expect(describeEvent({ kind: 'KEY_PRESS', detail: 'Escape' })).toBe('Pressed Esc')
    expect(describeEvent({ kind: 'KEY_PRESS', detail: 'F12' })).toBe('Pressed F12')
    expect(describeEvent({ kind: 'KEY_PRESS', detail: 'Ctrl+T' })).toBe('Pressed Ctrl+T')
    expect(describeEvent({ kind: 'KEY_PRESS', detail: 'Meta' })).toContain('Windows or Command key')
  })

  it('describes a stop, an ending and a reinstatement', () => {
    expect(describeEvent({ kind: 'STOPPED' })).toContain('their own choice')
    expect(describeEvent({ kind: 'ENDED', detail: 'TOO_MANY_LEAVES' })).toBe(
      'The interview ended because they left the interview screen too many times'
    )
    expect(describeEvent({ kind: 'ENDED', detail: 'TOO_LONG_AWAY' })).toContain('away from the interview screen for too long')
    expect(describeEvent({ kind: 'REINSTATED' })).toContain('reinstated')
  })

  it('is written the way the rest of the product is: no dashes, no exclamation marks', () => {
    const all = [
      { kind: 'LEFT_PAGE', detail: 'HIDDEN', duration_seconds: 1 },
      { kind: 'RELOAD', duration_seconds: 1 },
      { kind: 'KEY_PRESS', detail: 'Escape' },
      { kind: 'STOPPED' },
      { kind: 'ENDED', detail: 'TOO_LONG_AWAY' },
      { kind: 'REINSTATED' },
    ].map(describeEvent).join(' ') + STRICT_NOTE + endedText('TOO_MANY_LEAVES') + endedText('STOPPED')

    expect(all).not.toMatch(/[–—!]/)
  })

  it('never calls anything cheating, a violation or proof', () => {
    const all = ['TOO_MANY_LEAVES', 'TOO_LONG_AWAY', 'STOPPED'].map(endedText).join(' ')

    expect(all).not.toMatch(/cheat|violat|suspicio|caught|guilty/i)
  })
})

describe('the fixed note', () => {
  it('says the notes are for review, are not proof, and that nothing has been decided', () => {
    expect(STRICT_NOTE).toContain('for you to review')
    expect(STRICT_NOTE).toContain('not proof of anything')
    expect(STRICT_NOTE).toContain('no decision has been made for you')
  })
})

describe('small helpers', () => {
  it('titles a question and a follow-up', () => {
    expect(turnTitle({ kind: 'QUESTION', number: 2 })).toBe('Question 2')
    expect(turnTitle({ kind: 'FOLLOW_UP', number: 2 })).toBe('Follow-up to question 2')
  })

  it('writes a date and time, or a dash', () => {
    expect(formatWhen('2026-10-20T09:00:05Z')).toMatch(/2026/)
    expect(formatWhen(null)).toBe('-')
  })

  it('names the statuses that ended early, and no other', () => {
    expect(endedBadge('ENDED_CONDUCT')).toBe('Ended early')
    expect(endedBadge('STOPPED')).toBe('Stopped by the candidate')
    expect(endedBadge('SCORED')).toBeNull()
    expect(isEndedStatus('STOPPED')).toBe(true)
    expect(isEndedStatus('ENDED_CONDUCT')).toBe(true)
    expect(isEndedStatus('UPLOADED')).toBe(false)
  })
})
