import { describe, it, expect } from 'vitest'
import { interviewPricingNote, interviewsForCredits } from './interviewPricing'

describe('interviewsForCredits', () => {
  const pricing = { credits_per_interview: 10, balance: 0, charged: true }

  it('says how many whole interviews a number of credits buys', () => {
    expect(interviewsForCredits(10, pricing)).toBe(1)
    expect(interviewsForCredits(50, pricing)).toBe(5)
    expect(interviewsForCredits(150, pricing)).toBe(15)
    expect(interviewsForCredits(19, pricing)).toBe(1)
    expect(interviewsForCredits(9, pricing)).toBe(0)
  })

  it('has no answer when interviews are not charged for this account, or pricing is missing', () => {
    expect(interviewsForCredits(50, { credits_per_interview: 10, balance: null, charged: false })).toBeNull()
    expect(interviewsForCredits(50, null)).toBeNull()
    expect(interviewsForCredits(50, { credits_per_interview: 0, balance: 5, charged: true })).toBeNull()
  })
})

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

  it('tells a subscriber how much of the balance is their plan credits', () => {
    const note = interviewPricingNote({
      credits_per_interview: 10,
      balance: 47,
      charged: true,
      plan_credits: 40,
      purchased_credits: 7,
    })

    expect(note.text).toContain('Your balance: 47 (40 of them included in your plan this month)')
    expect(note.short).toBe(false)
  })

  it('does not mention plan credits when there are none', () => {
    const note = interviewPricingNote({
      credits_per_interview: 10,
      balance: 12,
      charged: true,
      plan_credits: 0,
      purchased_credits: 12,
    })

    expect(note.text).toContain('Your balance: 12.')
    expect(note.text).not.toContain('plan')
  })

  it('shows nothing when no charge applies to this account', () => {
    expect(interviewPricingNote({ credits_per_interview: 10, balance: null, charged: false })).toBeNull()
  })

  it('shows nothing until the pricing has loaded, or if it could not', () => {
    expect(interviewPricingNote(null)).toBeNull()
    expect(interviewPricingNote(undefined)).toBeNull()
  })
})
