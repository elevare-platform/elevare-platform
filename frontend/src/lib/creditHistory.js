// How one line of GET /api/v1/credits/transactions is shown. The server sends the
// wording (`description`, `detail`); this decides the sign, the colour and the
// "where did these credits come from" line.

const MINUS = '−'

export function describeChange(item) {
  const change = item.credits_change
  const amount = change > 0 ? `+${change}` : `${MINUS}${Math.abs(change)}`
  const plan = Math.abs(item.plan_credits_change)
  const bought = Math.abs(item.purchased_credits_change)

  let source = null
  if (plan > 0 && bought > 0) source = `${plan} plan · ${bought} bought`
  else if (plan > 0) source = 'plan credits'
  else if (bought > 0) source = 'bought credits'

  return { amount, tone: change > 0 ? 'in' : 'out', source }
}
