import { describe, it, expect } from 'vitest'
import {
  ENDED_FOOTER,
  KEY_WARNING,
  awayCause,
  awayTone,
  endedMessage,
  leaveNotice,
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
  const key = (init) => ({ key: 'a', ctrlKey: false, altKey: false, shiftKey: false, metaKey: false, ...init })

  it.each([
    [{ key: 'Escape' }, 'Escape'],
    [{ key: 'Alt', altKey: true }, 'Alt'],
    [{ key: 'Meta', metaKey: true }, 'Meta'],
    [{ key: 'OS' }, 'Meta'],
    [{ key: 'F11' }, 'F11'],
    [{ key: 'F12' }, 'F12'],
    [{ key: 'F5' }, 'F5'],
  ])('reports the single key %j as %s', (init, name) => {
    expect(reportableKey(key(init))).toBe(name)
  })

  it.each([
    [{ key: 't', ctrlKey: true }, 'Ctrl+T'],
    [{ key: 'W', ctrlKey: true }, 'Ctrl+W'],
    [{ key: 'n', metaKey: true }, 'Meta+N'],
    [{ key: 'Tab', ctrlKey: true }, 'Ctrl+Tab'],
    [{ key: 'Tab', altKey: true }, 'Alt+Tab'],
    [{ key: 'I', ctrlKey: true, shiftKey: true }, 'Ctrl+Shift+I'],
    [{ key: 'j', ctrlKey: true, shiftKey: true }, 'Ctrl+Shift+J'],
    [{ key: 'c', ctrlKey: true }, 'Ctrl+C'],
    [{ key: 'v', ctrlKey: true }, 'Ctrl+V'],
    [{ key: 'ArrowLeft', altKey: true }, 'Alt+Left'],
    [{ key: 'F4', altKey: true }, 'Alt+F4'],
    [{ key: ' ', ctrlKey: true }, 'Ctrl+Space'],
    [{ key: ',', ctrlKey: true }, 'Ctrl+Other'],
    [{ key: 'Backspace', ctrlKey: true, altKey: true, shiftKey: true, metaKey: true }, 'Ctrl+Alt+Shift+Meta+Backspace'],
  ])('reports the whole combination %j as %s', (init, name) => {
    expect(reportableKey(key(init))).toBe(name)
  })

  it('always writes a combination in the same order, whatever order the keys were pressed', () => {
    expect(reportableKey(key({ key: 'i', shiftKey: true, ctrlKey: true }))).toBe('Ctrl+Shift+I')
    expect(reportableKey(key({ key: 'i', ctrlKey: true, shiftKey: true }))).toBe('Ctrl+Shift+I')
  })

  it('never makes a name longer than the server keeps (40 characters)', () => {
    const longest = reportableKey(key({ key: 'Backspace', ctrlKey: true, altKey: true, shiftKey: true, metaKey: true }))

    expect(longest.length).toBeLessThanOrEqual(40)
  })

  it.each([
    [{ key: 'a' }],
    [{ key: 'A', shiftKey: true }],
    [{ key: 'Enter' }],
    [{ key: 'Tab' }],
    [{ key: ' ' }],
    [{ key: 'Control', ctrlKey: true }],
    [{ key: 'Shift', shiftKey: true }],
  ])('does not report %j', (init) => {
    expect(reportableKey(key(init))).toBeNull()
  })
})

describe('leaveNotice', () => {
  const state = (over) => ({ leaves: 1, max_leaves: 4, away_seconds: 12, max_away_seconds: 60, ended: null, ...over })

  it('says nothing before the first leave, or once the interview has ended', () => {
    expect(leaveNotice(state({ leaves: 0 }))).toBeNull()
    expect(leaveNotice(state({ ended: 'TOO_MANY_LEAVES' }))).toBeNull()
    expect(leaveNotice(null)).toBeNull()
  })

  it('counts the warnings used out of the ones allowed (one fewer than the leaves that end it)', () => {
    expect(leaveNotice(state({ leaves: 1 }))).toMatchObject({ used: 1, allowed: 3, last: false })
    expect(leaveNotice(state({ leaves: 2 }))).toMatchObject({ used: 2, allowed: 3, last: false })
    expect(leaveNotice(state({ leaves: 3 }))).toMatchObject({ used: 3, allowed: 3, last: true })
  })

  it('says what one more leave costs and how much time away is left', () => {
    const { lines } = leaveNotice(state({ leaves: 1, away_seconds: 12 }))

    expect(lines[0]).toContain('If you leave it 3 more times')
    expect(lines[0]).toContain('more than 48 more seconds in total')
  })

  it('counts down the leaves left, and switches to the last warning when one is left', () => {
    expect(leaveNotice(state({ leaves: 2 })).lines[0]).toContain('2 more times,')
    expect(leaveNotice(state({ leaves: 3 })).lines[0]).not.toContain('more times')
  })

  it('says plainly that it is the last warning', () => {
    const { lines, last } = leaveNotice(state({ leaves: 3, away_seconds: 40 }))

    expect(last).toBe(true)
    expect(lines[0]).toContain('This was your last warning')
    expect(lines[0]).toContain('more than 20 more seconds')
  })

  it('says the time for the question is still running', () => {
    expect(leaveNotice(state()).lines.at(-1)).toBe('The time for your question is still running.')
  })

  it('uses the limits the server sent, not fixed numbers', () => {
    const { allowed, lines } = leaveNotice(state({ max_leaves: 6, max_away_seconds: 90, leaves: 1, away_seconds: 10 }))

    expect(allowed).toBe(5)
    expect(lines[0]).toContain('5 more times')
    expect(lines[0]).toContain('80 more seconds')
  })

  it('never goes below zero seconds', () => {
    expect(leaveNotice(state({ leaves: 1, away_seconds: 75 })).lines[0]).toContain('more than 0 more seconds')
  })

  it('is written the way the rest of the product is: no dashes, no exclamation marks, no accusations', () => {
    const text = [1, 2, 3].map((leaves) => leaveNotice(state({ leaves })).lines.join(' ')).join(' ')

    expect(text).not.toMatch(/[–—!]/)
    expect(text).not.toMatch(/cheat|violat|suspicio|caught/i)
  })
})

describe('awayTone', () => {
  const at = (seconds) => awayTone({ away_seconds: seconds, max_away_seconds: 60 })

  it.each([
    [0, 'text-text-muted'],
    [29, 'text-text-muted'],
    [30, 'text-amber-700'],
    [47, 'text-amber-700'],
    [48, 'text-red-600'],
    [60, 'text-red-600'],
  ])('colours %s seconds of 60 as %s', (seconds, colour) => {
    expect(at(seconds)).toContain(colour)
  })

  it('follows the limit the server sent, not 60', () => {
    expect(awayTone({ away_seconds: 45, max_away_seconds: 90 })).toContain('text-amber-700')
    expect(awayTone({ away_seconds: 72, max_away_seconds: 90 })).toContain('text-red-600')
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
      .join(' ') + ENDED_FOOTER + KEY_WARNING

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
