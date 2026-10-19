import { Link } from 'react-router-dom'
import { Check, X } from 'lucide-react'
import { useOnboarding } from '@/hooks/useOnboarding'
import { cn } from '@/lib/utils'

/**
 * The "Get started" card on the employer dashboard.
 *
 * Profile, verification and first job are worked out from data the dashboard already
 * has, so they can never disagree with the account. The rest are opened-this-page steps
 * kept on the server. The card hides itself once everything is done, and can be
 * dismissed.
 */
export default function GetStartedChecklist({ user, stats, onShowTour }) {
  const { loaded, completedSteps, checklistDismissed, dismissChecklist } = useOnboarding()

  // Wait for both answers so nothing flashes from "not done" to "done".
  if (!loaded || checklistDismissed || stats == null) return null

  const profileDone = Boolean(user?.is_profile_complete)
  const verified = user?.kyc_status === 'APPROVED'
  const underReview = user?.kyc_status === 'PENDING'
  const seen = (step) => completedSteps.includes(step)

  const items = [
    {
      key: 'profile',
      label: 'Complete your company profile',
      done: profileDone,
      to: '/employer/onboarding',
    },
    {
      key: 'verify',
      label: 'Verify your company',
      done: verified,
      note: underReview ? 'Under review' : null,
      to: '/employer/verification',
    },
    {
      key: 'job',
      label: 'Post your first job',
      done: (stats.total_jobs ?? 0) > 0,
      to: '/employer/jobs/new',
    },
    { key: 'talent', label: 'Open the talent pool', done: seen('talent_pool'), to: '/employer/talent-pool' },
    {
      key: 'search',
      label: 'Try candidate search',
      done: seen('candidate_search'),
      to: '/employer/candidate-search',
    },
    { key: 'cv', label: 'Read and score CVs', done: seen('cv_parser'), to: '/employer/cv-parser' },
    {
      key: 'interviews',
      label: 'Try the interview list',
      done: seen('interview_list'),
      note: 'Open a job, then its interview list',
      to: '/employer/jobs',
    },
    { key: 'credits', label: 'Check your credits', done: seen('credits'), to: '/employer/billing' },
  ]

  const doneCount = items.filter((item) => item.done).length
  if (doneCount === items.length) return null

  return (
    <section
      aria-labelledby="get-started-title"
      data-tour="get-started"
      className="bg-white rounded-xl border border-border p-5"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 id="get-started-title" className="font-semibold text-text text-sm">Get started</h2>
          <p className="text-xs text-text-muted mt-0.5">
            {doneCount} of {items.length} done
            {onShowTour && (
              <>
                {' · '}
                <button
                  type="button"
                  onClick={onShowTour}
                  className="text-brand-blue font-medium hover:underline cursor-pointer"
                >
                  Show me around
                </button>
              </>
            )}
          </p>
        </div>
        <button
          type="button"
          onClick={dismissChecklist}
          aria-label="Hide the Get started list"
          className="p-1 -m-1 text-text-muted hover:text-text rounded cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
        >
          <X size={16} />
        </button>
      </div>

      <div
        className="mt-3 h-1.5 rounded-full bg-slate-100 overflow-hidden"
        role="progressbar"
        aria-label="Get started progress"
        aria-valuemin={0}
        aria-valuemax={items.length}
        aria-valuenow={doneCount}
      >
        <div
          className="h-full bg-brand-blue transition-[width] motion-reduce:transition-none"
          style={{ width: `${(doneCount / items.length) * 100}%` }}
        />
      </div>

      <ul className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1">
        {items.map((item) => (
          <li key={item.key}>
            <Link
              to={item.to}
              className="flex items-center gap-2.5 py-1.5 text-sm rounded hover:text-brand-blue focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
            >
              <span
                aria-hidden="true"
                className={cn(
                  'w-5 h-5 rounded-full flex items-center justify-center shrink-0 border',
                  item.done ? 'bg-green-500 border-green-500 text-white' : 'border-slate-300',
                )}
              >
                {item.done && <Check size={12} strokeWidth={3} />}
              </span>
              <span className={cn(item.done ? 'text-text-muted line-through' : 'text-text')}>
                {item.label}
                <span className="sr-only">{item.done ? ' (done)' : ' (not done yet)'}</span>
                {!item.done && item.note && (
                  <span className="block text-xs text-text-muted">{item.note}</span>
                )}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
