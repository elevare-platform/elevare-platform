import { describe, it, expect } from 'vitest'
import { CV_MISSING, joinList, missingForCompletion } from './profileCompleteness'

const FILLED = { bio: 'Sales professional', skills: ['Negotiation'], years_of_experience: '4', location: 'Lagos' }

describe('missingForCompletion', () => {
  it('finds nothing missing in a full profile with a CV', () => {
    expect(missingForCompletion(FILLED, 1)).toEqual([])
  })

  it('names only the CV when only the CV is missing', () => {
    expect(missingForCompletion(FILLED, 0)).toEqual([CV_MISSING])
  })

  it('does not blame the CV when the skills are the problem, as it used to', () => {
    expect(missingForCompletion({ ...FILLED, skills: [] }, 2)).toEqual(['skills'])
  })

  it('names every empty field, in the order the form shows them, and the CV last', () => {
    expect(missingForCompletion({ bio: '', skills: [], years_of_experience: '', location: '' }, 0)).toEqual([
      'about you',
      'skills',
      'years of experience',
      'location',
      CV_MISSING,
    ])
  })

  it('counts zero years of experience as filled in, as the server does', () => {
    expect(missingForCompletion({ ...FILLED, years_of_experience: '0' }, 1)).toEqual([])
    expect(missingForCompletion({ ...FILLED, years_of_experience: 0 }, 1)).toEqual([])
  })

  it('treats a missing value as empty rather than failing', () => {
    expect(missingForCompletion({}, 1)).toEqual(['about you', 'skills', 'years of experience', 'location'])
    expect(missingForCompletion(null, 1)).toHaveLength(4)
  })

  it('is written the way the rest of the product is: no dashes, no exclamation marks', () => {
    const all = missingForCompletion({}, 0).join(' ')
    expect(all).not.toMatch(/[–—!]/)
  })
})

describe('joinList', () => {
  it.each([
    [[], ''],
    [['skills'], 'skills'],
    [['skills', 'a CV'], 'skills and a CV'],
    [['bio', 'skills', 'a CV'], 'bio, skills and a CV'],
  ])('writes %j as %j', (items, expected) => {
    expect(joinList(items)).toBe(expected)
  })
})
