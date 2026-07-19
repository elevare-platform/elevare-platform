import { useState, useEffect } from 'react'
import {
  User, MapPin, Briefcase, DollarSign, Clock, GraduationCap,
  Award, FileText, Star, ExternalLink, Globe, X,
} from 'lucide-react'
import api from '@/lib/api'

/**
 * CandidateProfilePanel — slide-in panel showing a self-registered candidate's
 * full profile (bio, skills, work experience, education, CVs, links).
 *
 * Shared between ApplicantsPage's "View profile" action and TalentMatchCard's
 * "View Full Profile" action (shown once an introduction is ACCEPTED, at
 * which point the backend bypasses the candidate's visibility setting for
 * this specific employer).
 */
export default function CandidateProfilePanel({ profileId, jobId, onClose }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [restricted, setRestricted] = useState(false)

  useEffect(() => {
    setLoading(true)
    setRestricted(false)
    const params = jobId ? { job_id: jobId } : {}
    api.get(`/api/v1/candidates/${profileId}`, { params })
      .then(({ data }) => setProfile(data))
      .catch((err) => {
        if (err.response?.status === 403 || err.response?.status === 404) {
          setRestricted(true)
        }
        setProfile(null)
      })
      .finally(() => setLoading(false))
  }, [profileId, jobId])

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" aria-hidden="true" />

      {/* Panel */}
      <div
        className="relative w-full max-w-md bg-white h-full overflow-y-auto shadow-xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Candidate profile"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border sticky top-0 bg-white z-10">
          <h2 className="font-semibold text-text">Candidate Profile</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close panel"
            className="p-1.5 rounded-md text-text-muted hover:text-text hover:bg-surface-muted transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 px-6 py-5">
          {loading && (
            <div className="space-y-4 animate-pulse">
              <div className="flex items-center gap-3">
                <div className="w-14 h-14 rounded-full bg-gray-200" />
                <div className="space-y-2 flex-1">
                  <div className="h-4 bg-gray-200 rounded w-1/2" />
                  <div className="h-3 bg-gray-200 rounded w-1/3" />
                </div>
              </div>
              {[1,2,3].map((i) => <div key={i} className="h-16 bg-gray-200 rounded" />)}
            </div>
          )}

          {!loading && !profile && (
            <p className="text-sm text-text-muted text-center py-10">
              {restricted
                ? 'This candidate has restricted their profile visibility.'
                : 'Profile not available.'}
            </p>
          )}

          {!loading && profile && (
            <div className="space-y-6">
              {/* Identity */}
              <div className="flex items-center gap-4">
                <span className="w-14 h-14 rounded-full bg-brand-blue/10 flex items-center justify-center flex-shrink-0">
                  <User size={24} className="text-brand-blue" />
                </span>
                <div>
                  <p className="font-semibold text-text text-base">
                    {profile.first_name
                      ? `${profile.first_name} ${profile.last_name ?? ''}`.trim()
                      : 'Candidate'}
                  </p>
                  <div className="flex flex-wrap gap-x-3 text-xs text-text-muted mt-0.5">
                    {profile.location && (
                      <span className="flex items-center gap-1"><MapPin size={11} />{profile.location}</span>
                    )}
                    {profile.years_of_experience != null && (
                      <span className="flex items-center gap-1"><Briefcase size={11} />{profile.years_of_experience} yrs exp</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Bio */}
              {profile.bio && (
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-1.5">About</p>
                  <p className="text-sm text-text leading-relaxed">{profile.bio}</p>
                </div>
              )}

              {/* Skills */}
              {profile.skills?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">Skills</p>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.skills.map((s) => (
                      <span key={s} className="px-2.5 py-1 rounded-full bg-brand-blue/10 text-brand-blue text-xs font-medium">{s}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Salary + notice period */}
              {(profile.expected_salary || profile.notice_period_days != null) && (
                <div className="grid grid-cols-2 gap-3">
                  {profile.expected_salary && (
                    <div className="flex items-center gap-2 text-xs text-text-muted">
                      <DollarSign size={13} className="flex-shrink-0" />
                      <span>
                        {profile.expected_currency ?? ''} {Number(profile.expected_salary).toLocaleString()}
                      </span>
                    </div>
                  )}
                  {profile.notice_period_days != null && (
                    <div className="flex items-center gap-2 text-xs text-text-muted">
                      <Clock size={13} className="flex-shrink-0" />
                      <span>{profile.notice_period_days} day notice</span>
                    </div>
                  )}
                </div>
              )}

              {/* Work experience */}
              {profile.work_experiences?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">Work Experience</p>
                  <div className="space-y-3">
                    {profile.work_experiences.map((w) => (
                      <div key={w.id} className="border-l-2 border-brand-blue/30 pl-3">
                        <p className="text-sm font-medium text-text">{w.job_title}</p>
                        <p className="text-xs text-text-muted">{w.company_name}</p>
                        <p className="text-xs text-text-muted">
                          {w.start_date ?? 'Unknown'} to {w.is_current ? 'Present' : (w.end_date ?? 'Unknown')}
                        </p>
                        {w.description && (
                          <p className="text-xs text-text-muted mt-1 line-clamp-2">{w.description}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Education */}
              {profile.educations?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">Education</p>
                  <div className="space-y-3">
                    {profile.educations.map((e) => (
                      <div key={e.id} className="flex items-start gap-2">
                        <GraduationCap size={14} className="text-text-muted flex-shrink-0 mt-0.5" />
                        <div>
                          <p className="text-sm font-medium text-text">{e.degree} in {e.field_of_study}</p>
                          <p className="text-xs text-text-muted">{e.institution_name}</p>
                          {(e.start_year || e.end_year) && (
                          <p className="text-xs text-text-muted">{e.start_year ?? 'Unknown'} to {e.end_year ?? 'Present'}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Certifications */}
              {profile.certifications?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">Certifications</p>
                  <div className="space-y-2">
                    {profile.certifications.map((c) => (
                      <div key={c.id} className="flex items-start gap-2">
                        <Award size={14} className="text-text-muted flex-shrink-0 mt-0.5" />
                        <div>
                          <p className="text-sm font-medium text-text">{c.name}</p>
                          <p className="text-xs text-text-muted">{c.issuing_organization}</p>
                          {c.credential_url && (
                            <a href={c.credential_url} target="_blank" rel="noopener noreferrer"
                              className="text-xs text-brand-blue hover:underline">View credential</a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* CVs */}
              {profile.cvs?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">CVs</p>
                  <ul className="space-y-2">
                    {profile.cvs.map((cv) => (
                      <li key={cv.id} className="flex items-center gap-2 text-sm text-text">
                        <FileText size={14} className="text-brand-blue flex-shrink-0" />
                        <span className="truncate flex-1">{cv.filename}</span>
                        {cv.is_default && (
                          <span className="flex items-center gap-0.5 text-[10px] font-semibold text-brand-blue">
                            <Star size={10} />Default
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Links */}
              {(profile.linkedin_url || profile.github_url || profile.portfolio_url) && (
                <div>
                  <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">Links</p>
                  <div className="space-y-1.5">
                    {profile.linkedin_url && (
                      <a href={profile.linkedin_url} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-2 text-xs text-brand-blue hover:underline">
                        <ExternalLink size={13} />LinkedIn
                      </a>
                    )}
                    {profile.github_url && (
                      <a href={profile.github_url} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-2 text-xs text-brand-blue hover:underline">
                        <ExternalLink size={13} />GitHub
                      </a>
                    )}
                    {profile.portfolio_url && (
                      <a href={profile.portfolio_url} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-2 text-xs text-brand-blue hover:underline">
                        <Globe size={13} />Portfolio
                      </a>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
