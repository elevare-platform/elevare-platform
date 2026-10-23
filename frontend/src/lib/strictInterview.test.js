import { describe, it, expect } from 'vitest'
import {
  checkDevice,
  formatClock,
  pickAnswerMimeType,
  pickInterviewMimeType,
  shouldBlockKey,
  turnLabel,
} from './strictInterview'

const CHROME_LAPTOP = {
  userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
  brands: ['Chromium', 'Google Chrome', 'Not.A/Brand'],
  mobile: false,
  hasGetUserMedia: true,
  hasMediaRecorder: true,
  canRecordWebm: true,
  hasFullscreen: true,
  extendedDesktop: false,
}

const ids = (env) => checkDevice(env).problems.map((problem) => problem.id)

describe('checkDevice', () => {
  it('lets a laptop with Chrome through', () => {
    expect(checkDevice(CHROME_LAPTOP)).toEqual({ ok: true, problems: [] })
  })

  it('lets Edge through', () => {
    expect(ids({ ...CHROME_LAPTOP, brands: ['Chromium', 'Microsoft Edge'] })).toEqual([])
  })

  it('lets a Chrome that cannot tell about a second screen through, since it can only refuse what it knows', () => {
    expect(ids({ ...CHROME_LAPTOP, extendedDesktop: null })).toEqual([])
  })

  it('turns a phone away, first', () => {
    const phone = {
      ...CHROME_LAPTOP,
      userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/126.0.0.0 Mobile Safari/537.36',
      mobile: true,
    }
    expect(ids(phone)[0]).toBe('device')
  })

  it('turns a tablet away even when the browser does not say it is mobile', () => {
    const ipad = { ...CHROME_LAPTOP, brands: null, mobile: null, userAgent: 'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 CriOS/126 Mobile/15E148' }
    expect(ids(ipad)).toContain('device')
  })

  it.each([
    ['Firefox', { brands: null, userAgent: 'Mozilla/5.0 (Windows NT 10.0; rv:127.0) Gecko/20100101 Firefox/127.0' }],
    ['Safari', { brands: null, userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15' }],
    ['Opera', { brands: null, userAgent: 'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36 OPR/110.0.0.0' }],
    ['Brave', { brands: ['Chromium', 'Brave'] }],
  ])('turns %s away', (_name, override) => {
    expect(ids({ ...CHROME_LAPTOP, ...override })).toContain('browser')
  })

  it('judges an older Chrome by its user agent when it gives no brands', () => {
    expect(ids({ ...CHROME_LAPTOP, brands: null })).toEqual([])
    expect(ids({ ...CHROME_LAPTOP, brands: null, userAgent: 'Mozilla/5.0 Edg/126.0.0.0 Chrome/126.0.0.0' })).toEqual([])
  })

  it('turns a browser that cannot record or go full screen away', () => {
    expect(ids({ ...CHROME_LAPTOP, hasMediaRecorder: false })).toContain('recording')
    expect(ids({ ...CHROME_LAPTOP, canRecordWebm: false })).toContain('recording')
    expect(ids({ ...CHROME_LAPTOP, hasGetUserMedia: false })).toContain('recording')
    expect(ids({ ...CHROME_LAPTOP, hasFullscreen: false })).toContain('fullscreen')
  })

  it('refuses to start while a second screen is joined to the desktop', () => {
    const result = checkDevice({ ...CHROME_LAPTOP, extendedDesktop: true })

    expect(result.ok).toBe(false)
    expect(result.problems).toEqual([expect.objectContaining({ id: 'second-screen' })])
    expect(result.problems[0].message).toMatch(/disconnect/i)
  })

  it('reports every problem at once, so the candidate fixes them in one go', () => {
    const result = checkDevice({ ...CHROME_LAPTOP, brands: ['Brave'], extendedDesktop: true, hasFullscreen: false })

    expect(result.problems.map((problem) => problem.id)).toEqual(['browser', 'fullscreen', 'second-screen'])
  })

  it('is written the way the rest of the product is: no dashes, no exclamation marks', () => {
    const all = checkDevice({
      userAgent: 'x',
      brands: null,
      mobile: true,
      hasGetUserMedia: false,
      hasMediaRecorder: false,
      canRecordWebm: false,
      hasFullscreen: false,
      extendedDesktop: true,
    }).problems.map((problem) => problem.message).join(' ')

    expect(all).not.toMatch(/[–—!]/)
  })
})

describe('shouldBlockKey', () => {
  const key = (init) => ({ key: 'a', ctrlKey: false, altKey: false, metaKey: false, ...init })

  it.each([
    ['Ctrl+T', { key: 't', ctrlKey: true }],
    ['Ctrl+W', { key: 'w', ctrlKey: true }],
    ['Ctrl+Tab', { key: 'Tab', ctrlKey: true }],
    ['Alt+Tab', { key: 'Tab', altKey: true }],
    ['Cmd+N', { key: 'n', metaKey: true }],
    ['F5', { key: 'F5' }],
    ['F11', { key: 'F11' }],
    ['F12', { key: 'F12' }],
    ['PrintScreen', { key: 'PrintScreen' }],
    ['the Windows key', { key: 'Meta' }],
    ['the menu key', { key: 'ContextMenu' }],
  ])('blocks %s', (_name, init) => {
    expect(shouldBlockKey(key(init))).toBe(true)
  })

  it.each([['Tab'], ['Enter'], [' '], ['a']])('leaves plain %s alone, so the Next button can be reached', (pressed) => {
    expect(shouldBlockKey(key({ key: pressed }))).toBe(false)
  })
})

describe('formatClock', () => {
  it.each([
    [0, '0:00'],
    [5, '0:05'],
    [65, '1:05'],
    [600, '10:00'],
    [-3, '0:00'],
    [59.6, '1:00'],
  ])('writes %s seconds as %s', (seconds, expected) => {
    expect(formatClock(seconds)).toBe(expected)
  })
})

describe('turnLabel', () => {
  it('numbers a question out of all of them', () => {
    expect(turnLabel({ kind: 'QUESTION', number: 2 }, 5)).toBe('Question 2 of 5')
  })

  it('says which question a follow-up belongs to', () => {
    expect(turnLabel({ kind: 'FOLLOW_UP', number: 2 }, 5)).toBe('Follow-up to question 2')
  })

  it('is empty before there is a question', () => {
    expect(turnLabel(null, 5)).toBe('')
  })
})

describe('the recording formats', () => {
  const recorder = (supported) => ({ isTypeSupported: (type) => supported.includes(type) })

  it('records each answer as opus audio when it can, otherwise plain webm audio', () => {
    expect(pickAnswerMimeType(recorder(['audio/webm;codecs=opus', 'audio/webm']))).toBe('audio/webm;codecs=opus')
    expect(pickAnswerMimeType(recorder(['audio/webm']))).toBe('audio/webm')
    expect(pickAnswerMimeType(recorder([]))).toBeNull()
    expect(pickAnswerMimeType(null)).toBeNull()
  })

  it('records the whole interview as the best webm video it can', () => {
    expect(pickInterviewMimeType(recorder(['video/webm;codecs=vp9,opus', 'video/webm']))).toBe('video/webm;codecs=vp9,opus')
    expect(pickInterviewMimeType(recorder(['video/webm']))).toBe('video/webm')
    expect(pickInterviewMimeType(recorder(['video/mp4']))).toBeNull()
  })
})
