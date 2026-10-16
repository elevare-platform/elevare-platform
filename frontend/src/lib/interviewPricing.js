// What the interview list tells an employer about the cost of an AI interview,
// from GET /api/v1/interviews/pricing. Null means there is nothing to show:
// nothing is charged for this account (Elevare's own admin accounts, an owner
// with no organization, or a price of 0).
export function interviewPricingNote(pricing) {
  if (!pricing || !pricing.charged) return null
  const { credits_per_interview: cost, balance } = pricing
  return {
    text:
      `Each AI interview costs ${cost} credits, taken when you first send it. ` +
      'Resending is free, and the credits come back if the link expires unused. ' +
      `Your balance: ${balance}.`,
    // Not enough for one more: the note turns into a nudge to buy credits.
    short: balance < cost,
  }
}
