import { useState } from 'react'
import { MapPin, Briefcase, Clock, User, Sparkles, ChevronDown, ChevronUp, Send, Bell, CheckCircle2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import CandidateProfilePanel from '@/components/candidates/CandidateProfilePanel'
import SourcedCvModal from '@/components/employer/SourcedCvModal'
import CandidateActionModal from '@/components/employer/CandidateActionModal'
import SaveHeartButton from '@/components/employer/SaveHeartButton'
import { matchScoreBand } from '@/lib/matchScore'

/**
 * CandidateSearchResultCard  -  one ranked, explainable result from the
 * structured candidate search. Access to a candidate's full profile/CV
 * mirrors TalentMatchCard's workflow on the job-matching page exactly,
 * rather than exposing it unconditionally:
 *
 * - self_registered: CandidateProfilePanel  -  the candidate's own visibility
 *   setting is enforced server-side at GET /candidates/{id}.
 * - own_sourced: SourcedCvModal directly  -  the employer already owns this
 *   upload, no request needed.
 * - admin_sourced: gated behind `has_cv_access` (an accepted introduction).
 *   Until then, the action is "Request Introduction" via CandidateActionModal,
 *   not a free view.
 */
export default function CandidateSearchResultCard({ result, savedCandidates }) {
  const { profile, match_score: matchScore, matched_skills: matchedSkills, explanation } = result
  const band = matchScoreBand(matchScore)
  const displayName = profile.candidate_name || 'Private profile'

  const [showPanel, setShowPanel] = useState(false)
  const [showCvModal, setShowCvModal] = useState(false)
  const [showActionModal, setShowActionModal] = useState(false)
  const [requested, setRequested] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const isSelfRegistered = profile.ownership === 'self_registered' && profile.candidate_profile_id
  const isOwnSourced = profile.ownership === 'own_sourced'
  const canViewCv = isSelfRegistered || isOwnSourced || profile.has_cv_access

  const handlePrimaryAction = () => {
    if (isSelfRegistered) return setShowPanel(true)
    if (canViewCv) return setShowCvModal(true)
    setShowActionModal(true)
  }

  return (
    <div className="rounded-xl border border-border bg-white p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-start gap-4">
        <div
          className={cn(
            'px-2.5 py-1.5 rounded-full border text-xs font-bold flex-shrink-0 whitespace-nowrap',
            band.className
          )}
          title={`Raw score: ${Math.round(matchScore)}/100`}
        >
          {band.label}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <User size={16} className="text-text-muted flex-shrink-0" />
            <p className="font-semibold text-text text-sm truncate flex-1">{displayName}</p>
            {savedCandidates && (
              <SaveHeartButton
                saved={savedCandidates.isSaved({ talentPoolProfileId: profile.id })}
                onToggle={() => savedCandidates.toggle({ talentPoolProfileId: profile.id })}
              />
            )}
          </div>

          {(profile.current_title || profile.profession) && (
            <p className="text-xs text-text-muted mt-0.5">{profile.current_title || profile.profession}</p>
          )}

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1.5 text-xs text-text-muted">
            {profile.location && (
              <span className="flex items-center gap-1"><MapPin size={12} />{profile.location}</span>
            )}
            {profile.years_of_experience != null && (
              <span className="flex items-center gap-1"><Briefcase size={12} />{profile.years_of_experience} yrs experience</span>
            )}
            {profile.notice_period_days != null && (
              <span className="flex items-center gap-1"><Clock size={12} />{profile.notice_period_days}d notice</span>
            )}
          </div>

          {profile.summary && (
            <p className="text-xs text-text-muted mt-2 leading-relaxed">{profile.summary}</p>
          )}

          {profile.skills?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {profile.skills.map((skill) => (
                <span
                  key={skill}
                  className={cn(
                    'px-2 py-0.5 rounded-full text-[11px] border',
                    matchedSkills?.includes(skill)
                      ? 'bg-brand-blue/10 border-brand-blue/30 text-brand-blue font-medium'
                      : 'bg-gray-50 border-gray-200 text-text-muted'
                  )}
                >
                  {skill}
                </span>
              ))}
            </div>
          )}

          {explanation?.length > 0 && (
            <div className="mt-3 rounded-lg bg-brand-blue/5 border border-brand-blue/10 p-3">
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="flex items-center gap-1.5 text-xs font-medium text-brand-blue"
              >
                <Sparkles size={12} />
                Why this result ranked here
                {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
              {expanded && (
                <ul className="mt-2 space-y-1 text-xs text-text-muted list-disc list-inside">
                  {explanation.map((line, i) => <li key={i}>{line}</li>)}
                </ul>
              )}
            </div>
          )}

          {requested ? (
            <span className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-green-700">
              <CheckCircle2 size={13} /> {isOwnSourced ? 'Candidate notified' : 'Introduction requested'}
            </span>
          ) : (
            <button
              type="button"
              onClick={handlePrimaryAction}
              className="mt-3 text-xs font-medium text-brand-blue hover:underline flex items-center gap-1"
            >
              {isSelfRegistered
                ? 'View Full Profile'
                : canViewCv
                  ? 'View CV'
                  : isOwnSourced
                    ? <><Bell size={12} /> Notify Candidate</>
                    : <><Send size={12} /> Request Introduction</>}
            </button>
          )}
        </div>
      </div>

      {showPanel && (
        <CandidateProfilePanel profileId={profile.candidate_profile_id} onClose={() => setShowPanel(false)} />
      )}
      {showCvModal && (
        <SourcedCvModal profileId={profile.id} onClose={() => setShowCvModal(false)} />
      )}
      {showActionModal && (
        <CandidateActionModal
          match={profile}
          onClose={() => setShowActionModal(false)}
          onSuccess={() => { setRequested(true); setShowActionModal(false) }}
        />
      )}
    </div>
  )
}
