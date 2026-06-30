import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ChevronDown, ChevronUp, User } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

function scoreColour(score) {
  if (score == null) return 'bg-gray-100 text-gray-500'
  if (score <= 40) return 'bg-red-100 text-red-600'
  if (score <= 70) return 'bg-amber-100 text-amber-700'
  return 'bg-green-100 text-green-700'
}

function ApplicantCard({ applicant, rank }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="rounded-xl border border-border bg-white overflow-hidden">
      <div className="flex items-center gap-4 p-4">
        {/* Rank */}
        <span className="w-7 h-7 rounded-full bg-surface-muted text-text-muted text-xs font-semibold flex items-center justify-center flex-shrink-0">
          {rank}
        </span>

        {/* Avatar */}
        <span className="w-10 h-10 rounded-full bg-brand-blue/10 flex items-center justify-center flex-shrink-0" aria-hidden="true">
          <User size={18} className="text-brand-blue" />
        </span>

        {/* Name / initials */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-semibold text-text text-sm">
              {applicant.full_name ?? applicant.initials}
            </p>
            {applicant.source === 'external' && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-purple-50 text-purple-600 border border-purple-200">
                External CV
              </span>
            )}
          </div>
          {applicant.cv_snippet && (
            <p className="text-xs text-text-muted mt-0.5 line-clamp-1">{applicant.cv_snippet}</p>
          )}
        </div>

        {/* AI score */}
        <span className={cn(
          'w-12 h-12 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0',
          scoreColour(applicant.ai_score)
        )}>
          {applicant.ai_score != null ? `${applicant.ai_score}` : '—'}
        </span>

        {/* Expand toggle */}
        {(applicant.ai_fit_summary || applicant.ai_strengths?.length > 0) && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            aria-label={expanded ? 'Collapse details' : 'Expand details'}
            className="text-text-muted hover:text-text transition-colors"
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        )}
      </div>

      {/* Expanded reasoning */}
      {expanded && (
        <div className="border-t border-border px-4 py-4 bg-surface-muted space-y-3">
          {applicant.ai_fit_summary && (
            <p className="text-sm text-text leading-relaxed">{applicant.ai_fit_summary}</p>
          )}
          {applicant.ai_strengths?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-green-700 uppercase tracking-wide mb-1">Strengths</p>
              <ul className="space-y-1">
                {applicant.ai_strengths.map((s, i) => (
                  <li key={i} className="text-xs text-text flex items-start gap-2">
                    <span className="text-green-500 mt-0.5">✓</span>{s}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {applicant.ai_weaknesses?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-1">Considerations</p>
              <ul className="space-y-1">
                {applicant.ai_weaknesses.map((w, i) => (
                  <li key={i} className="text-xs text-text flex items-start gap-2">
                    <span className="text-amber-500 mt-0.5">·</span>{w}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function SharedApplicantsPage() {
  const { token } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [invalid, setInvalid] = useState(false)

  useEffect(() => {
    api.get(`/api/v1/public/jobs/${token}/applicants`)
      .then(({ data }) => setData(data))
      .catch((err) => {
        if (err.response?.status === 404) setInvalid(true)
      })
      .finally(() => setLoading(false))
  }, [token])

  if (loading) {
    return (
      <div className="min-h-screen bg-surface-muted flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-brand-blue border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (invalid) {
    return (
      <div className="min-h-screen bg-surface-muted flex items-center justify-center px-4">
        <div className="text-center max-w-sm">
          <p className="text-2xl font-bold text-text mb-2">Link no longer active</p>
          <p className="text-sm text-text-muted">This link has expired or been revoked. Contact the recruiter for an updated link.</p>
        </div>
      </div>
    )
  }

  const expiryDate = data?.expires_at
    ? new Date(data.expires_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
    : null

  return (
    <div className="min-h-screen bg-surface-muted">
      <div className="max-w-2xl mx-auto px-4 py-10 space-y-6">
        {/* Header */}
        <div className="space-y-1">
          <p className="text-xs font-semibold text-text-muted uppercase tracking-wide">Shared applicant list</p>
          <h1 className="text-2xl font-bold text-text">{data?.job_title}</h1>
          {expiryDate && (
            <p className="text-xs text-text-muted">This link expires on {expiryDate}</p>
          )}
        </div>

        {/* Consent notice */}
        <div className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-3 text-xs text-blue-800">
          Some candidates are displayed with initials only due to individual privacy preferences.
        </div>

        {/* Applicant list */}
        {data?.applicants?.length === 0 ? (
          <p className="text-sm text-text-muted text-center py-10">No applicants to display.</p>
        ) : (
          <div className="space-y-3">
            {(data?.applicants ?? []).map((applicant, i) => (
              <ApplicantCard key={i} applicant={applicant} rank={i + 1} />
            ))}
          </div>
        )}

        <p className="text-xs text-text-muted text-center pt-4">
          Powered by Elevare Human Solutions
        </p>
      </div>
    </div>
  )
}
