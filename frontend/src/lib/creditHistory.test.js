import { describe, it, expect } from 'vitest'
import { describeChange } from './creditHistory'

const item = (credits, plan, bought) => ({
  credits_change: credits,
  plan_credits_change: plan,
  purchased_credits_change: bought,
})

describe('describeChange', () => {
  it('shows credits coming in with a plus sign', () => {
    expect(describeChange(item(40, 40, 0))).toEqual({
      amount: '+40',
      tone: 'in',
      source: 'plan credits',
    })
  })

  it('shows credits spent with a minus sign', () => {
    expect(describeChange(item(-10, 0, -10))).toEqual({
      amount: '−10',
      tone: 'out',
      source: 'bought credits',
    })
  })

  it('says how a spend was split between plan and bought credits', () => {
    expect(describeChange(item(-10, -6, -4))).toEqual({
      amount: '−10',
      tone: 'out',
      source: '6 plan · 4 bought',
    })
  })

  it('says how a refund was split between plan and bought credits', () => {
    expect(describeChange(item(10, 6, 4)).source).toBe('6 plan · 4 bought')
  })
})
