import { describe, it, expect } from 'vitest'
import {
  INTERVIEW_RULES_VERSION,
  MONITORING,
  RULE_GROUPS,
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
