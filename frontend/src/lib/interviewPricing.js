// How many whole AI interviews a number of credits buys, so a credit pack can say
// "about 5 AI interviews" instead of leaving the buyer to do the sum. Null when
// interviews are not charged for this account (or the pricing is not known).
export function interviewsForCredits(credits, pricing) {
  if (!pricing || !pricing.charged || pricing.credits_per_interview <= 0) return null
  return Math.floor(credits / pricing.credits_per_interview)
}

// What the interview list tells an employer about the cost of an AI interview,
// from GET /api/v1/interviews/pricing. Null means there is nothing to show:
// nothing is charged for this account (Elevare's own admin accounts, an owner
// with no organization, or a price of 0).
export function interviewPricingNote(pricing) {
  if (!pricing || !pricing.charged) return null
  const { credits_per_interview: cost, balance, plan_credits: planCredits } = pricing
  // Plan credits are spent first; say how many of the balance they are, so a
  // subscriber sees why the number goes down by less than they bought.
  const split = planCredits > 0 ? ` (${planCredits} of them included in your plan this month)` : ''
  return {
    text:
      `Each AI interview costs ${cost} credits, taken when you first send it. ` +
      'Resending is free, and the credits come back if the link expires unused. ' +
      `Your balance: ${balance}${split}.`,
    // Not enough for one more: the note turns into a nudge to buy credits.
    short: balance < cost,
  }
}
