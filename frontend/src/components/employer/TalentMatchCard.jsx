import { MapPin, Briefcase, Sparkles, User } from 'lucide-react'
import { cn } from '@/lib/utils'

function scoreTier(score) {
  if (score == null) return 'grey'
  if (score >= 75) return 'green'
  if (score >= 50) return 'amber'
  return 'grey'
}

const SCORE_STYLES = {
  green: { ring: 'border-green-500', text: 'text-green-700', glow: 'from-green-500/20' },
  amber: { ring: 'border-amber-500', text: 'text-amber-700', glow: 'from-amber-500/20' },
  grey: { ring: 'border-gray-300', text: 'text-gray-500', glow: 'from-gray-400/10' },
}

export default function TalentMatchCard({ match }) {
  const tier = scoreTier(match.similarity_score)
  const styles = SCORE_STYLES[tier]
  const displayName = match.candidate_name ?? 'Private profile'

  return (
    <div className="group relative rounded-2xl border border-border bg-white p-5 overflow-hidden transition-all hover:shadow-lg hover:-translate-y-0.5">
      {/* Soft gradient accent — stronger for higher-similarity matches */}
      <div
        className={cn(
          'pointer-events-none absolute -top-12 -right-12 w-36 h-36 rounded-full bg-gradient-to-br to-transparent blur-2xl opacity-70 transition-opacity group-hover:opacity-100',
          styles.glow
        )}
        aria-hidden="true"
      />

      <div className="relative flex items-start gap-4">
        <span className="w-11 h-11 rounded-full bg-brand-blue/10 flex items-center justify-center flex-shrink-0">
          <User size={18} className="text-brand-blue" />
        </span>

        <div className="flex-1 min-w-0">
          <p className="font-semibold text-text text-sm truncate">{displayName}</p>
          {match.current_title && (
            <p className="text-xs text-text-muted truncate mt-0.5">{match.current_title}</p>
          )}
          <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs text-text-muted">
            {match.location && (
              <span className="flex items-center gap-1">
                <MapPin size={11} />
                {match.location}
              </span>
            )}
            {match.years_of_experience != null && (
              <span className="flex items-center gap-1">
                <Briefcase size={11} />
                {match.years_of_experience} yr{match.years_of_experience !== 1 ? 's' : ''} exp
              </span>
            )}
          </div>
        </div>

        <div
          className={cn(
            'flex items-center justify-center w-14 h-14 rounded-full border-2 flex-shrink-0 bg-white',
            styles.ring
          )}
          title={`${match.similarity_score}% similarity to this job`}
        >
          <span className={cn('text-sm font-bold leading-none', styles.text)}>
            {match.similarity_score}%
          </span>
        </div>
      </div>

      {match.top_skills?.length > 0 && (
        <div className="relative flex flex-wrap gap-1.5 mt-4">
          {match.top_skills.map((skill) => (
            <span
              key={skill}
              className="px-2.5 py-1 rounded-full bg-surface-muted text-text text-[11px] font-medium border border-border"
            >
              {skill}
            </span>
          ))}
        </div>
      )}

      {tier === 'green' && (
        <div className="relative flex items-center gap-1 mt-3 text-[11px] font-semibold text-green-600">
          <Sparkles size={11} />
          Strong match
        </div>
      )}
    </div>
  )
}
