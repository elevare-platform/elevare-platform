import { useState, useEffect } from 'react'
import { X, Users, Brain } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

function scoreColor(s) {
  if (s == null) return 'bg-gray-100 text-gray-500'
  if (s >= 75) return 'bg-green-100 text-green-700'
  if (s >= 50) return 'bg-amber-100 text-amber-700'
  return 'bg-red-100 text-red-600'
}

/**
 * SourcedCvModal — shown for sourced-only talent pool profiles (no
 * CandidateProfile, no login) once an introduction has been ACCEPTED.
 * There's no separate "profile" to view for these — the parsed CV data
 * itself, fetched by profile ID, is the full extent of what's available.
 */
export default function SourcedCvModal({ profileId, onClose }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(false)
    api.get(`/api/v1/talent-pool/${profileId}`)
      .then(({ data }) => { if (!cancelled) setProfile(data) })
      .catch(() => { if (!cancelled) setError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [profileId])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" aria-hidden="true" />
      <div
        className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Candidate CV"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-border sticky top-0 bg-white z-10">
          <h2 className="font-semibold text-text">Candidate CV</h2>
          <button onClick={onClose} className="p-1.5 rounded-md text-text-muted hover:text-text hover:bg-surface-muted transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-6">
          {loading && (
            <div className="space-y-4 animate-pulse">
              <div className="flex items-center gap-3">
                <div className="w-14 h-14 rounded-full bg-gray-200" />
                <div className="space-y-2 flex-1">
                  <div className="h-4 bg-gray-200 rounded w-1/2" />
                  <div className="h-3 bg-gray-200 rounded w-1/3" />
                </div>
              </div>
              <div className="h-20 bg-gray-200 rounded" />
            </div>
          )}

          {!loading && (error || !profile) && (
            <p className="text-sm text-text-muted text-center py-10">CV not available.</p>
          )}

          {!loading && !error && profile && (
            <>
              {/* Identity */}
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-full bg-brand-blue/10 flex items-center justify-center flex-shrink-0">
                  <Users size={24} className="text-brand-blue" />
                </div>
                <div>
                  <p className="font-semibold text-text text-base">
                    {profile.candidate_name ?? profile.candidate_email ?? 'Unnamed Candidate'}
                  </p>
                  {profile.candidate_current_title && (
                    <p className="text-sm text-text-muted mt-0.5">{profile.candidate_current_title}</p>
                  )}
                  {profile.candidate_email && (
                    <p className="text-xs text-text-muted">{profile.candidate_email}</p>
                  )}
                </div>
              </div>

              {/* AI Score */}
              {profile.ai_score != null && (
                <div className="rounded-xl border border-border p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-text-muted uppercase tracking-wide flex items-center gap-1.5">
                      <Brain size={12} /> AI Assessment
                    </p>
                    <span className={cn('px-2.5 py-0.5 rounded-full text-sm font-bold', scoreColor(profile.ai_score))}>
                      {profile.ai_score}/100
                    </span>
                  </div>
                  {profile.ai_fit_summary && (
                    <p className="text-sm text-text leading-relaxed">{profile.ai_fit_summary}</p>
                  )}
                  {profile.ai_strengths?.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-green-700 uppercase tracking-wide mb-1">Strengths</p>
                      <ul className="space-y-1">
                        {profile.ai_strengths.map((s, i) => (
                          <li key={i} className="text-xs text-text flex items-start gap-1.5">
                            <span className="text-green-500 mt-0.5 flex-shrink-0">✓</span>{s}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {profile.ai_weaknesses?.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-1">Considerations</p>
                      <ul className="space-y-1">
                        {profile.ai_weaknesses.map((w, i) => (
                          <li key={i} className="text-xs text-text flex items-start gap-1.5">
                            <span className="text-amber-500 mt-0.5 flex-shrink-0">·</span>{w}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Source info */}
              <div>
                <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">Source</p>
                <div className="flex items-center gap-2 text-sm text-text">
                  <span className="capitalize">{profile.source}</span>
                  {profile.source_note && <span className="text-text-muted">({profile.source_note})</span>}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
