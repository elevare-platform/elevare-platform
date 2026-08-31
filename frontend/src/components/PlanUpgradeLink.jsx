import { Link } from 'react-router-dom'

// Inline CTA appended after a plan/limit error message — same link target
// and wording everywhere it appears (job posting quota, candidate search
// block, talent pool scoring gate, ...).
export default function PlanUpgradeLink({ className = 'underline font-medium' }) {
  return (
    <>
      {' '}
      -{' '}
      <Link to="/pricing" className={className}>
        Upgrade plan
      </Link>
    </>
  )
}
