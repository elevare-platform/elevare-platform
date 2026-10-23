import { describe, it, expect } from 'vitest'
import {
  INTERVIEW_RULES_VERSION,
  MONITORING,
  RULE_GROUPS,
  STRICT_MONITORING,
  STRICT_RULES_VERSION,
  STRICT_RULE_GROUPS,
  numberedRuleGroups,
  visibleRuleGroups,
} from './interviewRules'

const allRules = RULE_GROUPS.flatMap((group) => group.rules)
const ALL_ON = { tabSwitch: true, faceChecks: true, gaze: true }
const ALL_OFF = { tabSwitch: false, faceChecks: false, gaze: false }

describe('the interview rules', () => {
  it('have a version, so a record can say which wording a candidate accepted', () => {
    expect(INTERVIEW_RULES_VERSION).toBeTruthy()
  })

  it('give every rule an id and some text, and no id twice', () => {
    const ids = allRules.map((rule) => rule.id)

    expect(allRules.every((rule) => rule.id && rule.text.length > 20)).toBe(true)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('are written the way the rest of the product is: no dashes, no exclamation marks', () => {
    for (const rule of allRules) {
      expect(rule.text, rule.id).not.toMatch(/[–—!]/)
    }
  })

  it('never tell a candidate something is watched unless the feature that watches it is on', () => {
    // A rule that says an event "is noted" or "are noted" describes monitoring, so it must wait
    // for its feature (`needs`). Otherwise a candidate could be told they are watched when not.
    const claimsMonitoring = allRules.filter((rule) => /\bnoted\b/i.test(rule.text))

    expect(claimsMonitoring.length).toBeGreaterThan(0)
    expect(claimsMonitoring.every((rule) => rule.needs)).toBe(true)
  })

  it('only point at features that exist in the switch list', () => {
    for (const rule of allRules.filter((r) => r.needs)) {
      expect(Object.keys(MONITORING), rule.id).toContain(rule.needs)
    }
  })
})

describe('which rules are shown', () => {
  it('shows none of the monitoring rules today, because none of those features is built', () => {
    expect(MONITORING).toEqual(ALL_OFF)

    const shown = visibleRuleGroups().flatMap((group) => group.rules.map((rule) => rule.id))

    expect(shown).not.toContain('stay-on-page')
    expect(shown).not.toContain('face-visible')
    expect(shown).not.toContain('look-at-screen')
    expect(shown).toContain('camera-on')
    expect(shown).toContain('alone')
  })

  it('adds a rule the moment its feature is switched on', () => {
    const ids = (monitoring) =>
      visibleRuleGroups(monitoring).flatMap((group) => group.rules.map((rule) => rule.id))

    expect(ids({ ...ALL_OFF, tabSwitch: true })).toContain('stay-on-page')
    expect(ids({ ...ALL_OFF, tabSwitch: true })).not.toContain('look-at-screen')
    expect(ids({ ...ALL_OFF, gaze: true })).toContain('look-at-screen')
    expect(ids(ALL_ON).length).toBe(allRules.length)
  })

  it('never shows an empty group', () => {
    for (const monitoring of [ALL_OFF, ALL_ON]) {
      expect(visibleRuleGroups(monitoring).every((group) => group.rules.length > 0)).toBe(true)
    }
  })
})

describe('the strict interview rules', () => {
  const strictRules = STRICT_RULE_GROUPS.flatMap((group) => group.rules)
  const strictIds = (monitoring) =>
    visibleRuleGroups(monitoring, STRICT_RULE_GROUPS).flatMap((group) => group.rules.map((rule) => rule.id))

  it('have their own version, apart from the live interview rules', () => {
    expect(STRICT_RULES_VERSION).toBeTruthy()
    expect(STRICT_RULES_VERSION).not.toBe(INTERVIEW_RULES_VERSION)
  })

  it('give every rule an id and some text, and no id twice', () => {
    const ids = strictRules.map((rule) => rule.id)

    expect(strictRules.every((rule) => rule.id && rule.text.length > 20)).toBe(true)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('are written the way the rest of the product is: no dashes, no exclamation marks', () => {
    for (const rule of strictRules) {
      expect(rule.text, rule.id).not.toMatch(/[–—!]/)
    }
  })

  it('say nothing about the live voice interview, which they replace', () => {
    for (const rule of strictRules) {
      expect(rule.text, rule.id).not.toMatch(/headphones|earphones|restart|End interview button|interviewer/i)
    }
  })

  it('never tell a candidate something is watched unless the feature that watches it is on', () => {
    const claimsMonitoring = strictRules.filter((rule) => /\bnoted\b/i.test(rule.text))

    expect(claimsMonitoring.length).toBeGreaterThan(0)
    expect(claimsMonitoring.every((rule) => rule.needs)).toBe(true)
  })

  it('show the leaving, key and stop rules, because the strict screen really does those', () => {
    expect(STRICT_MONITORING.tabSwitch).toBe(true)
    const ids = strictIds(STRICT_MONITORING)

    expect(ids).toEqual(expect.arrayContaining(['stay-on-page', 'keys-noted', 'stop-button', 'if-it-ends']))
  })

  it('hide those rules when the monitoring is off, so nothing is ever promised that is not done', () => {
    const ids = strictIds(ALL_OFF)

    for (const id of ['stay-on-page', 'keys-noted', 'stop-button', 'if-it-ends']) expect(ids).not.toContain(id)
  })

  it('never show a face or gaze rule, since that is not built', () => {
    expect(STRICT_MONITORING.faceChecks).toBe(false)
    expect(STRICT_MONITORING.gaze).toBe(false)
    expect(strictIds(STRICT_MONITORING)).not.toContain('face-visible')
    expect(strictIds(STRICT_MONITORING)).not.toContain('look-at-screen')
  })

  it('leave the live interviews own switches alone, so the live rules still claim nothing', () => {
    expect(MONITORING).toEqual(ALL_OFF)
  })

  it('state the limits the server enforces: the first three leaves warn, the fourth or 60 seconds ends it', () => {
    const rule = strictRules.find((r) => r.id === 'stay-on-page')

    expect(rule.text).toContain('first three times you get a warning')
    expect(rule.text).toContain('The fourth time')
    expect(rule.text).toContain('60 seconds')
  })

  it('say the keys that are noted do not end the interview', () => {
    const rule = strictRules.find((r) => r.id === 'keys-noted')

    expect(rule.text).toContain('does not end the interview')
    for (const key of ['Esc', 'Alt', 'F11', 'F12']) expect(rule.text).toContain(key)
  })

  it('say that stopping is the candidates own choice, and what happens after an ending', () => {
    expect(strictRules.find((r) => r.id === 'stop-button').text).toContain('your choice')
    expect(strictRules.find((r) => r.id === 'if-it-ends').text).toContain('still sent to the employer')
    expect(strictRules.find((r) => r.id === 'employer-decides').text).toContain('not proof of anything')
  })

  it('state what the screen really does: laptops only, one screen, full screen', () => {
    const ids = strictIds(STRICT_MONITORING)

    expect(ids).toEqual(expect.arrayContaining(['laptop-and-browser', 'one-screen', 'full-screen', 'questions-on-screen', 'follow-up']))
  })

  it('are numbered from 1 with no gap', () => {
    for (const monitoring of [ALL_OFF, STRICT_MONITORING]) {
      const numbers = numberedRuleGroups(monitoring, STRICT_RULE_GROUPS).flatMap((group) =>
        group.rules.map((rule) => rule.number)
      )

      expect(numbers).toEqual(numbers.map((_, index) => index + 1))
    }
  })
})

describe('numbering', () => {
  it('counts on from group to group, from 1, with no gap', () => {
    for (const monitoring of [ALL_OFF, ALL_ON]) {
      const numbers = numberedRuleGroups(monitoring).flatMap((group) =>
        group.rules.map((rule) => rule.number)
      )

      expect(numbers).toEqual(numbers.map((_, index) => index + 1))
    }
  })

  it('renumbers when a rule is added, so the numbers never skip', () => {
    const off = numberedRuleGroups(ALL_OFF).flatMap((group) => group.rules)
    const on = numberedRuleGroups(ALL_ON).flatMap((group) => group.rules)

    expect(on.length).toBeGreaterThan(off.length)
    expect(on.at(-1).number).toBe(on.length)
  })
})
