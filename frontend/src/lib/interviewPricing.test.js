import { describe, it, expect } from 'vitest'
import { interviewPricingNote } from './interviewPricing'

describe('interviewPricingNote', () => {
  it('says what an interview costs, when it is charged, and the balance', () => {
    const note = interviewPricingNote({ credits_per_interview: 10, balance: 90, charged: true })

    expect(note.text).toContain('costs 10 credits')
    expect(note.text).toContain('when you first send it')
    expect(note.text).toContain('Resending is free')
    expect(note.text).toContain('Your balance: 90')
    expect(note.short).toBe(false)
  })

  it('flags a balance that cannot cover another interview', () => {
    expect(interviewPricingNote({ credits_per_interview: 10, balance: 9, charged: true }).short).toBe(true)
    expect(interviewPricingNote({ credits_per_interview: 10, balance: 10, charged: true }).short).toBe(false)
    expect(interviewPricingNote({ credits_per_interview: 10, balance: 0, charged: true }).short).toBe(true)
  })

  it('shows nothing when no charge applies to this account', () => {
    expect(interviewPricingNote({ credits_per_interview: 10, balance: null, charged: false })).toBeNull()
  })

  it('shows nothing until the pricing has loaded, or if it could not', () => {
    expect(interviewPricingNote(null)).toBeNull()
    expect(interviewPricingNote(undefined)).toBeNull()
  })
})
