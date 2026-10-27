import { describe, it, expect } from 'vitest'
import {
  DEFAULT_FOLLOW_UP_SECONDS,
  FOLLOW_UP_MODES,
  FOLLOW_UP_TIME_OPTIONS,
  MAX_PROBE_CHARS,
  MAX_QUESTION_CHARS,
  TIME_OPTIONS,
  blankQuestion,
  cleanText,
  formatSeconds,
  moveQuestion,
  probeLines,
  problemsWith,
  removeQuestion,
  timeLeftForFollowUps,
  totalSeconds,
} from './interviewQuestions'

const LIMITS = { max_questions: 40, max_total_seconds: 1200 }
const GOOD = 'Tell us about a time you handled a production outage.'
const q = (text = GOOD, seconds = 120) => ({ text, time_limit_seconds: seconds })

describe('the choices for the time to answer', () => {
  it('run from 30 seconds to 10 minutes in steps of 30 seconds', () => {
    expect(TIME_OPTIONS[0]).toBe(30)
    expect(TIME_OPTIONS.at(-1)).toBe(600)
    expect(TIME_OPTIONS).toHaveLength(20)
    expect(TIME_OPTIONS.every((value, index) => index === 0 || value - TIME_OPTIONS[index - 1] === 30)).toBe(true)
  })
})

describe('formatSeconds', () => {
  it.each([
    [30, '30 s'],
    [45, '45 s'],
    [60, '1 min'],
    [90, '1 min 30 s'],
    [120, '2 min'],
    [1200, '20 min'],
  ])('writes %i seconds as %s', (seconds, expected) => {
    expect(formatSeconds(seconds)).toBe(expected)
  })
})

describe('totals and tidying', () => {
  it('adds the times up, treating a missing time as nothing', () => {
    expect(totalSeconds([q(GOOD, 90), q(GOOD, 120), { text: GOOD }])).toBe(210)
    expect(totalSeconds([])).toBe(0)
  })

  it('collapses blanks the way the server does', () => {
    expect(cleanText('   Why   do you want    this role?  ')).toBe('Why do you want this role?')
    expect(cleanText(null)).toBe('')
  })
})

describe('a new question', () => {
  it('starts empty, written by the employer, with the usual two minutes', () => {
    expect(blankQuestion('k1')).toEqual({
      key: 'k1',
      text: '',
      time_limit_seconds: 120,
      source: 'EMPLOYER',
      probes: '',
      follow_up_seconds: null,
    })
  })
})

describe('the time to answer a follow-up', () => {
  it('runs from 30 seconds to 5 minutes in steps of 30 seconds, and includes the default of 90 seconds', () => {
    expect(FOLLOW_UP_TIME_OPTIONS[0]).toBe(30)
    expect(FOLLOW_UP_TIME_OPTIONS.at(-1)).toBe(300)
    expect(FOLLOW_UP_TIME_OPTIONS).toHaveLength(10)
    expect(FOLLOW_UP_TIME_OPTIONS).toContain(DEFAULT_FOLLOW_UP_SECONDS)
  })
})

describe('timeLeftForFollowUps', () => {
  it('is what is left of the interview after the answer times, and never below nothing', () => {
    const limits = { max_total_seconds: 1200 }

    expect(timeLeftForFollowUps([q(GOOD, 600), q(GOOD, 300)], limits)).toBe(300)
    expect(timeLeftForFollowUps([], limits)).toBe(1200)
    expect(timeLeftForFollowUps([q(GOOD, 600), q(GOOD, 600), q(GOOD, 600)], limits)).toBe(0)
  })
})

describe('probeLines', () => {
  it('splits the probes into tidy lines and drops the blank ones', () => {
    expect(probeLines('  What was your   part? \n\nHow big?\n  ')).toEqual(['What was your part?', 'How big?'])
    expect(probeLines(null)).toEqual([])
    expect(probeLines(undefined)).toEqual([])
  })
})

describe('the follow-up choices', () => {
  it('offers the three modes the server knows, the standard one first', () => {
    expect(FOLLOW_UP_MODES.map((mode) => mode.value)).toEqual(['STANDARD', 'PROBES_ONLY', 'NONE'])
    expect(FOLLOW_UP_MODES.every((mode) => mode.label && mode.help)).toBe(true)
  })

  it('is written the way the rest of the product is: no dashes, no exclamation marks', () => {
    const all = FOLLOW_UP_MODES.map((mode) => `${mode.label} ${mode.help}`).join(' ')

    expect(all).not.toMatch(/[–—!]/)
  })
})

describe('moving and removing questions', () => {
  const list = [q('A'), q('B'), q('C')]

  it('moves a question up or down by one place, without changing the original list', () => {
    expect(moveQuestion(list, 1, -1).map((x) => x.text)).toEqual(['B', 'A', 'C'])
    expect(moveQuestion(list, 1, 1).map((x) => x.text)).toEqual(['A', 'C', 'B'])
    expect(list.map((x) => x.text)).toEqual(['A', 'B', 'C'])
  })

  it('does nothing at the ends', () => {
    expect(moveQuestion(list, 0, -1)).toBe(list)
    expect(moveQuestion(list, 2, 1)).toBe(list)
  })

  it('removes the one asked for', () => {
    expect(removeQuestion(list, 1).map((x) => x.text)).toEqual(['A', 'C'])
    expect(list).toHaveLength(3)
  })
})

describe('problemsWith, the same rules as the server', () => {
  it('finds nothing wrong with a good list or an empty one', () => {
    expect(problemsWith([q(), q(GOOD, 300)], LIMITS)).toEqual([])
    expect(problemsWith([], LIMITS)).toEqual([])
  })

  it('has no limit on how many questions, only on their total time', () => {
    expect(problemsWith(Array.from({ length: 12 }, () => q(GOOD, 60)), LIMITS)).toEqual([])
    expect(problemsWith(Array.from({ length: 11 }, () => q(GOOD, 120)), LIMITS)).toHaveLength(1)
  })

  it('refuses too many or too long probes, and counts blank lines and repeated blanks as nothing', () => {
    const many = { ...q(), probes: Array.from({ length: 7 }, (_, n) => `Probe ${n}?`).join('\n') }
    const long = { ...q(), probes: 'x'.repeat(MAX_PROBE_CHARS + 1) }
    const fine = { ...q(), probes: '\n  What was your   part?  \n\n' }

    expect(problemsWith([many], LIMITS)).toEqual(['Question 1 has too many probes. Keep it to 6.'])
    expect(problemsWith([q(), long], LIMITS)).toEqual([
      'A probe on question 2 is too long. Keep each under 300 characters.',
    ])
    expect(problemsWith([fine], LIMITS)).toEqual([])
  })

  it('names a too short or too long question by its number', () => {
    const problems = problemsWith([q(), q('Why?'), q('x'.repeat(MAX_QUESTION_CHARS + 1))], LIMITS)

    expect(problems).toContain('Question 2 is too short to be a question.')
    expect(problems.find((p) => p.startsWith('Question 3 is too long'))).toBeTruthy()
    expect(problems.some((p) => p.includes('Question 1'))).toBe(false)
  })

  it('does not count extra blanks towards the length', () => {
    expect(problemsWith([q('   a          b   ')], LIMITS)).toHaveLength(1)
  })

  it('says when the times do not fit the interview, and what to do', () => {
    const problems = problemsWith([q(GOOD, 300), q(GOOD, 300), q(GOOD, 300), q(GOOD, 300), q(GOOD, 120)], LIMITS)

    expect(problems).toEqual([
      'The answer times add up to 22 min, but the whole interview is limited to 20 min. Shorten some of the times.',
    ])
  })

  it('allows times that add up to exactly the limit', () => {
    expect(problemsWith(Array.from({ length: 4 }, () => q(GOOD, 300)), LIMITS)).toEqual([])
  })

  it('is written the way the rest of the product is: no dashes, no exclamation marks', () => {
    const all = problemsWith(
      [q('Why?'), q(GOOD, 600), q(GOOD, 600), q(GOOD, 600)].concat(Array.from({ length: 4 }, () => q())),
      LIMITS
    ).join(' ')

    expect(all).not.toMatch(/[–—!]/)
  })
})
