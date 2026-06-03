import { Link } from 'react-router-dom'
import { computeStrength, STRENGTH_FIELDS } from '@/lib/candidateUtils'

// Human-readable labels for each strength field (Requirement 3.4)
const FIELD_LABELS = {
  bio: 'About You',
  skills: 'Your Skills',
  years_of_experience: 'Years of Experience',
  location: 'Location',
}

/**
 * ProfileStrengthBar — displays a labeled progress bar showing how complete
 * the candidate's profile is, a checklist of missing fields, and a CTA.
 *
 * Props:
 *   profile — ProfileResponse object or null
 *
 * Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
 */
export function ProfileStrengthBar({ profile }) {
  const strength = computeStrength(profile)

  // Determine which strength fields are missing (Requirement 3.4)
  const missingFields = STRENGTH_FIELDS.filter((f) => {
    if (!profile) return true
    const v = profile[f]
    if (Array.isArray(v)) return v.length === 0
    return v === null || v === undefined || v === ''
  })

  const missingCV = !profile?.cvs || profile.cvs.length === 0

  // Color the bar based on strength level
  const barColor =
    strength === 100
      ? 'bg-green-500'
      : strength >= 50
        ? 'bg-brand-blue'
        : 'bg-brand-amber'

  return (
    <div className="rounded-lg border border-border bg-surface p-5 space-y-4">
      {/* Label + percentage — Requirement 3.2 */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-text">Profile Strength</span>
        <span className="text-sm font-semibold text-text">{strength}%</span>
      </div>

      {/* Progress bar — Requirement 3.2 */}
      <div className="w-full h-2 rounded-full bg-border overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${strength}%` }}
          role="progressbar"
          aria-valuenow={strength}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Profile strength: ${strength}%`}
        />
      </div>

      {/* Encouraging copy — Requirement 3.3 (shown when below 100%) */}
      {strength < 100 && (
        <p className="text-sm text-text-muted">
          Stronger profiles are prioritised by our recruiters.
        </p>
      )}

      {/* Missing fields checklist — Requirement 3.4 (shown when below 100%) */}
      {strength < 100 && missingFields.length > 0 && (
        <ul className="space-y-1">
          {missingFields.map((field) => (
            <li key={field} className="flex items-center gap-2 text-sm text-text-muted">
              <span className="w-4 h-4 rounded-full border-2 border-border flex-shrink-0" aria-hidden="true" />
              {FIELD_LABELS[field]}
            </li>
          ))}
          {missingCV && (
            <li className="flex items-center gap-2 text-sm text-text-muted">
              <span className="w-4 h-4 rounded-full border-2 border-border flex-shrink-0" aria-hidden="true" />
              Upload a CV
            </li>
          )}
        </ul>
      )}

      {/* CTA — Requirement 3.5 (always shown; label changes at 100%) */}
      <Link
        to="/candidate/profile"
        className="inline-block text-sm font-medium text-brand-blue hover:text-brand-blue-dark transition-colors"
      >
        {strength === 100 ? 'Edit Your Profile →' : 'Complete Your Profile →'}
      </Link>
    </div>
  )
}
