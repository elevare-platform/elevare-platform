import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ChevronDown, ChevronUp, Download, User } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import { AgeLabel } from '@/components/employer/TalentPoolFilters'

function scoreColour(score) {
  if (score == null) return 'bg-gray-100 text-gray-500'
  if (score <= 40) return 'bg-red-100 text-red-600'
  if (score <= 70) return 'bg-amber-100 text-amber-700'
  return 'bg-green-100 text-green-700'
}

function ApplicantCard({ applicant, rank, onOpened }) {
  const [expanded, setExpanded] = useState(false)
  // Opening the details or the CV is what makes a candidate "seen" on this link.
  const opened = () => onOpened?.(applicant)
  const toggle = () => {
    if (!expanded) opened()
    setExpanded((v) => !v)
  }

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
            {applicant.is_new_since_last_visit && (
              <span
                data-testid="new-since-badge"
                className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded-full bg-brand-blue text-white"
              >
                New
              </span>
            )}
            {applicant.is_unseen && (
              <span data-testid="unopened-badge" className="text-[10px] font-medium text-text-muted">
                Not opened yet
              </span>
            )}
          </div>
          {applicant.cv_snippet && (
            <p className="text-xs text-text-muted mt-0.5 line-clamp-1">{applicant.cv_snippet}</p>
          )}
          {/* The list is sorted by score, so show when each candidate arrived. */}
          <AgeLabel profile={applicant} verb={applicant.source === 'external' ? 'Added' : 'Applied'} />
        </div>

        {/* AI score */}
        <span className={cn(
          'w-12 h-12 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0',
          scoreColour(applicant.ai_score)
        )}>
          {applicant.ai_score != null ? `${applicant.ai_score}` : 'N/A'}
        </span>

        {/* CV download */}
        {applicant.cv_download_url && (
          <a
            href={applicant.cv_download_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={opened}
            aria-label="Download CV"
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-border text-xs text-text hover:bg-surface-muted transition-colors flex-shrink-0"
          >
            <Download size={12} />
            CV
          </a>
        )}

        {/* Expand toggle */}
        {(applicant.ai_fit_summary || applicant.ai_strengths?.length > 0) && (
          <button
            type="button"
            onClick={toggle}
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

const TAB_LABELS = { all: 'All', unseen: 'Not opened yet', new: 'New since your last visit' }

export default function SharedApplicantsPage() {
  const { token } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [invalid, setInvalid] = useState(false)
  const [tab, setTab] = useState('all')

  // The reader opened a candidate: it stops being "not opened" at once on screen, and the server
  // is told so it is remembered for this link on the next visit, on any device.
  const handleOpened = (applicant) => {
    if (!applicant.item_key || !applicant.is_unseen) return
    setData((current) => {
      if (!current) return current
      const applicants = current.applicants.map((a) => (a.item_key === applicant.item_key ? { ...a, is_unseen: false } : a))
      return { ...current, applicants, unseen_count: applicants.filter((a) => a.is_unseen).length }
    })
    api.post(`/api/v1/public/jobs/${token}/seen`, { item_key: applicant.item_key }).catch(() => {})
  }

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
          <h1 className="text-2xl font-bold text-text font-sans">{data?.job_title}</h1>
          {expiryDate && (
            <p className="text-xs text-text-muted">This link expires on {expiryDate}</p>
          )}
        </div>

        {/* Consent notice */}
        <div className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-3 text-xs text-blue-800">
          Some candidates are displayed with initials only due to individual privacy preferences.
        </div>

        {/* What is new for this reader: a nudge, and tabs to see only those. */}
        {data?.applicants?.length > 0 && (
          <div className="space-y-2" data-testid="seen-tabs">
            {data.previous_visit_at && data.new_since_last_visit_count > 0 && (
              <p className="rounded-lg border border-brand-blue/30 bg-brand-blue/5 px-4 py-2.5 text-sm text-text">
                {data.new_since_last_visit_count} new candidate{data.new_since_last_visit_count === 1 ? ' has' : 's have'} been
                added since your last visit on{' '}
                {new Date(data.previous_visit_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long' })}.
              </p>
            )}
            <div role="tablist" aria-label="Candidates" className="flex flex-wrap gap-2">
              {['all', 'unseen', ...(data.previous_visit_at && data.new_since_last_visit_count > 0 ? ['new'] : [])].map((key) => {
                const count = key === 'unseen' ? data.unseen_count : key === 'new' ? data.new_since_last_visit_count : null
                return (
                  <button
                    key={key}
                    type="button"
                    role="tab"
                    aria-selected={tab === key}
                    onClick={() => setTab(key)}
                    className={cn(
                      'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                      tab === key ? 'border-brand-blue bg-brand-blue text-white' : 'border-border bg-white text-text hover:bg-surface-muted'
                    )}
                  >
                    {TAB_LABELS[key]}{count != null ? ` (${count})` : ''}
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* Applicant list */}
        {data?.applicants?.length === 0 ? (
          <p className="text-sm text-text-muted text-center py-10">No applicants to display.</p>
        ) : (
          <div className="space-y-3">
            {(data?.applicants ?? []).map((applicant, i) => ({ applicant, rank: i + 1 }))
              .filter(({ applicant }) =>
                tab === 'unseen' ? applicant.is_unseen : tab === 'new' ? applicant.is_new_since_last_visit : true)
              .map(({ applicant, rank }) => (
                <ApplicantCard key={applicant.item_key ?? rank} applicant={applicant} rank={rank} onOpened={handleOpened} />
              ))}
            {tab !== 'all' && !data?.applicants?.some((a) => (tab === 'unseen' ? a.is_unseen : a.is_new_since_last_visit)) && (
              <p className="text-sm text-text-muted text-center py-8">
                {tab === 'unseen' ? 'You have opened every candidate on this list.' : 'Nothing new since your last visit.'}
              </p>
            )}
          </div>
        )}

        <p className="text-xs text-text-muted text-center pt-4">
          Powered by Elevare Human Solutions
        </p>
      </div>
    </div>
  )
}
