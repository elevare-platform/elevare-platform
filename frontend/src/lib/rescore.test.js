import { describe, it, expect } from 'vitest'
import { describeRescore } from './rescore'

const result = (overrides = {}) => ({
  scoring: 0, reparsing: 0, in_progress: 0, no_stored_file: 0, remaining: 0, ...overrides,
})

describe('describeRescore', () => {
  it('says nothing for no answer', () => {
    expect(describeRescore(null)).toBe('')
  })

  it('says how many were started, and how many CVs are being read again', () => {
    expect(describeRescore(result({ scoring: 3, reparsing: 2 })))
      .toBe('Started 5 candidates, 2 CVs are being read again.')
    expect(describeRescore(result({ reparsing: 1 })))
      .toBe('Started 1 candidate, 1 CV is being read again.')
  })

  it('says how many are left and what to do about it', () => {
    expect(describeRescore(result({ scoring: 25, remaining: 12 })))
      .toBe('Started 25 candidates. 12 still to do: press Rescore again to go on.')
  })

  it('explains the ones it could do nothing for', () => {
    const text = describeRescore(result({ in_progress: 2, no_stored_file: 1 }))

    expect(text).toContain('2 CVs are still being read')
    expect(text).toContain('1 CV could not be read and there is no stored file to read again, so it needs a new upload')
  })

  it('uses the plural for several CVs with no stored file', () => {
    expect(describeRescore(result({ no_stored_file: 3 }))).toContain('so they need a new upload')
  })

  it('says so when nothing needed doing', () => {
    expect(describeRescore(result())).toBe('Nothing needed rescoring.')
  })

  it('is written the way the rest of the product is: no dashes, no exclamation marks', () => {
    const text = describeRescore(result({ scoring: 1, reparsing: 1, in_progress: 1, no_stored_file: 1, remaining: 1 }))
    expect(text).not.toMatch(/[–—!]/)
  })
})
