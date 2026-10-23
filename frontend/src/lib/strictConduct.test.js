import { describe, it, expect } from 'vitest'
import {
  ENDED_FOOTER,
  KEY_WARNING,
  awayCause,
  endedMessage,
  leaveWarning,
  reasonFromStatus,
  reportableKey,
} from './strictConduct'

const doc = (over = {}) => ({ visibilityState: 'visible', hasFocus: () => true, fullscreenElement: {}, ...over })

describe('awayCause', () => {
  it('is none while the page is visible, in focus and full screen', () => {
    expect(awayCause(doc())).toBeNull()
  })

  it.each([
    ['another tab or app', { visibilityState: 'hidden' }, 'HIDDEN'],
    ['the window losing focus', { hasFocus: () => false }, 'BLUR'],
    ['leaving full screen', { fullscreenElement: null }, 'FULLSCREEN'],
  ])('says why for %s', (_name, over, cause) => {
    expect(awayCause(doc(over))).toBe(cause)
  })

  it('names one cause when several apply at once, since they are one leave', () => {
    expect(awayCause(doc({ visibilityState: 'hidden', hasFocus: () => false, fullscreenElement: null }))).toBe('HIDDEN')
    expect(awayCause(doc({ hasFocus: () => false, fullscreenElement: null }))).toBe('BLUR')
  })

  it('does not call a browser that cannot tell about focus away', () => {
    expect(awayCause(doc({ hasFocus: undefined }))).toBeNull()
  })
})

describe('reportableKey', () => {
  const key = (init) => ({ key: 'a', ctrlKey: false, metaKey: false, ...init })

  it.each([
    [{ key: 'Escape' }, 'Escape'],
    [{ key: 'Alt' }, 'Alt'],
    [{ key: 'Meta' }, 'Meta'],
    [{ key: 'OS' }, 'Meta'],
    [{ key: 'F11' }, 'F11'],
    [{ key: 'F12' }, 'F12'],
    [{ key: 't', ctrlKey: true }, 'Ctrl+T'],
    [{ key: 'W', ctrlKey: true }, 'Ctrl+W'],
    [{ key: 'n', metaKey: true }, 'Ctrl+N'],
    [{ key: 'Tab', ctrlKey: true }, 'Ctrl+Tab'],
  ])('reports %j as %s', (init, name) => {
    expect(reportableKey(key(init))).toBe(name)
  })

  it.each([
    [{ key: 'a' }],
    [{ key: 'Enter' }],
    [{ key: 'Tab' }],
    [{ key: 'c', ctrlKey: true }],
    [{ key: 'v', ctrlKey: true }],
    [{ key: 'F5' }],
    [{ key: 't' }],
  ])('does not report %j', (init) => {
    expect(reportableKey(key(init))).toBeNull()
  })
})

describe('leaveWarning', () => {
  const state = (over) => ({ leaves: 1, max_leaves: 4, away_seconds: 12, max_away_seconds: 60, ended: null, ...over })

  it('says nothing before the first leave, or once the interview has ended', () => {
    expect(leaveWarning(state({ leaves: 0 }))).toBeNull()
    expect(leaveWarning(state({ ended: 'TOO_MANY_LEAVES' }))).toBeNull()
    expect(leaveWarning(null)).toBeNull()
  })

  it('says how many times, what ends it and how much of the time away is used', () => {
    const text = leaveWarning(state({ leaves: 2, away_seconds: 31 }))

    expect(text).toContain('left the interview screen 2 times')
    expect(text).toContain('If you leave it 4 times')
    expect(text).toContain('more than 60 seconds')
    expect(text).toContain('away 31 of 60 seconds')
  })

  it('says "1 time" for the first', () => {
    expect(leaveWarning(state())).toContain('1 time.')
  })

  it('uses the limits the server sent, not fixed numbers', () => {
    expect(leaveWarning(state({ max_leaves: 6, max_away_seconds: 90 }))).toContain('6 times')
    expect(leaveWarning(state({ max_leaves: 6, max_away_seconds: 90 }))).toContain('90 seconds')
  })
})

describe('what the candidate is told when it ends', () => {
  it.each(['TOO_MANY_LEAVES', 'TOO_LONG_AWAY', 'STOPPED'])('has a title and a body for %s', (reason) => {
    const { title, body } = endedMessage(reason)

    expect(title.length).toBeGreaterThan(10)
    expect(body.length).toBeGreaterThan(20)
  })

  it('says a stop was the candidates own choice, and conduct reasons are about leaving the screen', () => {
    expect(endedMessage('STOPPED').title).toBe('You stopped the interview')
    expect(endedMessage('TOO_MANY_LEAVES').body).toContain('too many times')
    expect(endedMessage('TOO_LONG_AWAY').body).toContain('too long')
  })

  it('never calls anything cheating, a failure or a violation', () => {
    const all = ['TOO_MANY_LEAVES', 'TOO_LONG_AWAY', 'STOPPED']
      .map((reason) => Object.values(endedMessage(reason)).join(' '))
      .join(' ') + ENDED_FOOTER + KEY_WARNING + leaveWarning({ leaves: 1, max_leaves: 4, away_seconds: 1, max_away_seconds: 60 })

    expect(all).not.toMatch(/cheat|fail|violat|suspicio|caught|guilty/i)
  })

  it('is written the way the rest of the product is: no dashes, no exclamation marks', () => {
    const all = ['TOO_MANY_LEAVES', 'TOO_LONG_AWAY', 'STOPPED']
      .map((reason) => Object.values(endedMessage(reason)).join(' '))
      .join(' ') + ENDED_FOOTER + KEY_WARNING

    expect(all).not.toMatch(/[–—!]/)
  })

  it('tells the candidate their answers and recording were sent, and who to contact', () => {
    expect(ENDED_FOOTER).toContain('answers and your recording')
    expect(ENDED_FOOTER).toContain('contact the employer who invited you')
  })
})

describe('reasonFromStatus', () => {
  it('reads the reason an already ended interview shows from its status', () => {
    expect(reasonFromStatus('STOPPED')).toBe('STOPPED')
    expect(reasonFromStatus('ENDED_CONDUCT')).toBe('TOO_MANY_LEAVES')
    expect(reasonFromStatus('IN_PROGRESS')).toBeNull()
    expect(reasonFromStatus(undefined)).toBeNull()
  })
})
