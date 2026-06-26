import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

// ─── Score colour helper ──────────────────────────────────────────────────────

function scoreColour(score) {
  if (score == null) return 'bg-gray-100 text-gray-400'
  if (score >= 70) return 'bg-purple-100 text-purple-700'
  if (score >= 40) return 'bg-amber-100 text-amber-700'
  return 'bg-red-100 text-red-600'
}

// ─── Single applicant card ────────────────────────────────────────────────────

function PublicApplicantCard({ applicant, rank }) {
  const [expanded, setExpanded] = useState(false)
  const hasReasoning = applicant.ai_strengths?.length || applicant.ai_weaknesses?.length

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="flex items-center gap-4 p-4">
        {/* Rank */}
        <span className="w-8 h-8 rounded-full bg-gray-100 text-gray-500 text-xs font-bold flex items-center justify-center flex-shrink-0">
          {rank}
        </span>

        {/* Name / initials */}
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-gray-900 text-sm">
            {applicant.full_name ?? applicant.initials}
          </p>
          {applicant.cv_snippet && (
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{applicant.cv_snippet}</p>
          )}
        </div>

        {/* AI score */}
        <span className={cn(
          'flex-shrink-0 flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold',
          scoreColour(applicant.ai_score)
        )}>
          <span className="text-[9px] font-bold uppercase opacity-60">AI</span>
          {applicant.ai_score ?? '—'}
        </span>

        {/* Expand toggle */}
        {hasReasoning && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-label={expanded ? 'Collapse details' : 'Expand details'}
            className="text-gray-400 hover:text-gray-600 flex-shrink-0"
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        )}
      </div>

      {/* Fit summary */}
      {applicant.ai_fit_summary && (
        <div className="px-4 pb-3 -mt-1">
          <p className="text-xs text-gray-600 italic">{applicant.ai_fit_summary}</p>
        </div>
      )}

      {/* Expanded reasoning */}
      {expanded && (
        <div className="border-t border-gray-100 px-4 py-3 grid sm:grid-cols-2 gap-4 bg-gray-50">
          {applicant.ai_strengths?.length > 0 && (
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wide text-green-600 mb-1.5">Strengths</p>
              <ul className="space-y-1">
                {applicant.ai_strengths.map((s, i) => (
                  <li key={i} className="text-xs text-gray-700 flex gap-1.5">
                    <span className="text-green-500">✓</span>{s}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {applicant.ai_weaknesses?.length > 0 && (
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wide text-red-500 mb-1.5">Gaps</p>
              <ul className="space-y-1">
                {applicant.ai_weaknesses.map((w, i) => (
                  <li key={i} className="text-xs text-gray-700 flex gap-1.5">
                    <span className="text-red-400">·</span>{w}
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

// ─── SharedApplicantsPage ─────────────────────────────────────────────────────

export default function SharedApplicantsPage() {
  const { token } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [invalid, setInvalid] = useState(false)

  useEffect(() => {
    api.get(`/api/v1/public/jobs/${token}/applicants`)
      .then(({ data }) => setData(data))
      .catch((err) => {
        if (err.response?.status === 404 || err.response?.status === 410) {
          setInvalid(true)
        }
      })
      .finally(() => setLoading(false))
  }, [token])

  // Minimal chrome — no navbar, no footer, standalone page
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 py-12">

        {loading && (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 rounded-xl bg-gray-200 animate-pulse" />
            ))}
          </div>
        )}

        {!loading && invalid && (
          <div className="text-center py-24">
            <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl">🔒</span>
            </div>
            <h1 className="text-xl font-semibold text-gray-800 mb-2">
              This link is no longer active
            </h1>
            <p className="text-sm text-gray-500">
              The link may have expired or been revoked. Contact your recruiter for an updated link.
            </p>
          </div>
        )}

        {!loading && data && (
          <>
            {/* Header */}
            <div className="mb-8">
              <h1 className="text-2xl font-bold text-gray-900">{data.job_title}</h1>
              <p className="text-sm text-gray-500 mt-1">
                Ranked applicants · Link expires {new Date(data.expires_at).toLocaleDateString('en-GB', {
                  day: 'numeric', month: 'long', year: 'numeric',
                })}
              </p>

              {/* Privacy notice when there's a mix of named and initialled candidates */}
              <p className="mt-3 text-xs text-gray-400 border border-gray-200 rounded-lg px-3 py-2 bg-white">
                Some candidates are displayed with initials only due to individual privacy preferences.
              </p>
            </div>

            {/* Applicant list */}
            {data.applicants.length === 0 ? (
              <p className="text-center text-sm text-gray-500 py-16">No applicants to display yet.</p>
            ) : (
              <div className="space-y-3">
                {data.applicants.map((applicant, i) => (
                  <PublicApplicantCard key={i} applicant={applicant} rank={i + 1} />
                ))}
              </div>
            )}

            <p className="text-center text-xs text-gray-400 mt-10">
              Powered by Elevare Human Solutions
            </p>
          </>
        )}
      </div>
    </div>
  )
}
