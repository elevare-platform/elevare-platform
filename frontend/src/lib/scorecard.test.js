import { describe, it, expect } from 'vitest'
import { RATING_OPTIONS, evaluationDate, pointsText, ratingName, ratingText } from './scorecard'

describe('scorecard helpers', () => {
  it('offers ratings from 1 to 5 in steps of a half', () => {
    expect(RATING_OPTIONS).toEqual([1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5])
  })

  it('names a whole rating, and a half point as between two levels', () => {
    expect(ratingName(4)).toBe('Strong')
    expect(ratingName(3.5)).toBe('Competent to Strong')
    expect(ratingName(1.5)).toBe('Insufficient evidence to Limited')
  })

  it('writes a rating with one decimal as the printed scorecard does', () => {
    expect(ratingText(4)).toBe('4.0')
    expect(ratingText(3.5)).toBe('3.5')
    expect(ratingText(null)).toBe('Not assessed')
  })

  it('writes weighted points as the printed scorecard does: 12.0, 5.25, 1.5', () => {
    expect(pointsText(12)).toBe('12.0')
    expect(pointsText(5.25)).toBe('5.25')
    expect(pointsText(1.5)).toBe('1.5')
    expect(pointsText(37.5)).toBe('37.5')
    expect(pointsText(50)).toBe('50.0')
    expect(pointsText(2.2500001)).toBe('2.25')
  })

  it('writes the date of evaluation as October 28, 2026', () => {
    expect(evaluationDate('2026-10-28T12:00:00Z')).toBe('October 28, 2026')
    expect(evaluationDate(null)).toBe('')
  })
})
