import { describe, it, expect } from 'vitest'
import { matchScoreBand, scoreFailureHelp } from './matchScore'

describe('matchScoreBand', () => {
  it('bands a real score as before', () => {
    expect(matchScoreBand(78).label).toBe('Strong match')
    expect(matchScoreBand(52).label).toBe('Good match')
    expect(matchScoreBand(31).label).toBe('Fair match')
  })

  it('treats a score of 0 as a real score, not as missing', () => {
    expect(matchScoreBand(0).key).toBe('fair')
  })

  it('says "Not yet scored" when there is no score and no failure', () => {
    expect(matchScoreBand(null).label).toBe('Not yet scored')
    expect(matchScoreBand(undefined, null).label).toBe('Not yet scored')
  })

  it('says why when a CV could not be read', () => {
    const band = matchScoreBand(null, 'CV_UNREADABLE')

    expect(band.label).toBe('Could not read CV')
    expect(band.key).toBe('unreadable')
    expect(band.className).toContain('red')
  })

  it('says scoring was unavailable when the scoring call failed', () => {
    expect(matchScoreBand(null, 'SCORING_FAILED').label).toBe('Scoring unavailable')
  })

  it('says the plan limit when this month\'s AI scoring allowance is used up, not a failure', () => {
    const band = matchScoreBand(null, 'PLAN_LIMIT')

    expect(band.label).toBe('Not scored: plan limit')
    expect(band.key).toBe('plan_limit')
    expect(band.label).not.toMatch(/fail|unavailable|could not/i)
  })

  it('never lets a failure marker hide a real score', () => {
    expect(matchScoreBand(78, 'SCORING_FAILED').label).toBe('Strong match')
    expect(matchScoreBand(0, 'CV_UNREADABLE').label).toBe('Fair match')
    expect(matchScoreBand(55, 'PLAN_LIMIT').label).toBe('Good match')
  })

  it('does not invent a state for a failure it does not know', () => {
    expect(matchScoreBand(null, 'SOMETHING_NEW').label).toBe('Not yet scored')
  })
})

describe('scoreFailureHelp', () => {
  it('explains each failure in one plain sentence', () => {
    expect(scoreFailureHelp('CV_UNREADABLE')).toMatch(/Nothing could be read from this CV/)
    expect(scoreFailureHelp('SCORING_FAILED')).toMatch(/not a low score/)
    expect(scoreFailureHelp('PLAN_LIMIT')).toMatch(/AI scoring on your plan is used up/)
    expect(scoreFailureHelp('PLAN_LIMIT')).toMatch(/Upgrade your plan/)
  })

  it('has nothing to say when there is no failure', () => {
    expect(scoreFailureHelp(null)).toBeNull()
    expect(scoreFailureHelp(undefined)).toBeNull()
    expect(scoreFailureHelp('SOMETHING_NEW')).toBeNull()
  })

  it('is written the way the rest of the product is: no dashes, no exclamation marks', () => {
    for (const failure of ['CV_UNREADABLE', 'SCORING_FAILED', 'PLAN_LIMIT']) {
      expect(scoreFailureHelp(failure)).not.toMatch(/[–—!]/)
    }
  })
})
