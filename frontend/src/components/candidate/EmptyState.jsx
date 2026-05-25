import { Link } from 'react-router-dom'
import { ArrowRight, Sparkles } from 'lucide-react'
import { ProfileStrengthBar } from './ProfileStrengthBar'

/**
 * EmptyState — shown when a candidate has no CVs, no documents,
 * and no profile strength fields filled in.
 *
 * Requirements: 10.2, 10.3, 10.4, 10.5
 * Requirement 10.6 — ProfileStrengthBar is still rendered (showing 0%).
 *
 * Props:
 *   firstName  {string}          — from useAuth(); used in the heading
 *   profile    {object | null}   — passed through to ProfileStrengthBar
 */
export function EmptyState({ firstName, profile }) {
  return (
    <div className="flex flex-col gap-8">
      {/* Welcome card */}
      <div className="rounded-xl border border-border bg-surface p-8 text-center flex flex-col items-center gap-4">
        {/* Decorative icon */}
        <div
          className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-brand-blue/10"
          aria-hidden="true"
        >
          <Sparkles size={28} className="text-brand-blue" strokeWidth={1.5} />
        </div>

        {/* Requirement 10.2 — heading with first name */}
        <h1 className="text-2xl font-bold text-text">
          Welcome to Elevare, {firstName}.
        </h1>

        {/* Requirement 10.3 — subheading */}
        <p className="text-text-muted max-w-md leading-relaxed">
          Let&apos;s build your career profile. A complete profile helps our
          recruiters match you with the right opportunities.
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row items-center gap-3 mt-2">
          {/* Requirement 10.4 — primary CTA */}
          <Link
            to="/candidate/profile"
            className="inline-flex items-center gap-2 rounded-lg bg-brand-blue px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-blue/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2"
          >
            Complete Your Profile
            <ArrowRight size={15} strokeWidth={2} aria-hidden="true" />
          </Link>

          {/* Requirement 10.5 — secondary CTA */}
          <Link
            to="/jobs"
            className="inline-flex items-center gap-2 rounded-lg border border-border bg-white px-5 py-2.5 text-sm font-semibold text-text hover:bg-slate-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2"
          >
            Browse Open Roles
          </Link>
        </div>
      </div>

      {/* Requirement 10.6 — ProfileStrengthBar still rendered at 0% */}
      <ProfileStrengthBar profile={profile} />
    </div>
  )
}
