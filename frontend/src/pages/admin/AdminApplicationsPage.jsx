import { useEffect, useState, useCallback } from 'react'
import { Download, Star, Info, ChevronDown, ChevronUp } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'
import { AdminTable, Th, Td, Pagination } from '@/components/admin/AdminTable'
import StatusBadge from '@/components/admin/StatusBadge'
import { useToast } from '@/components/admin/Toast'
import { useAdmin } from '@/hooks/useAdmin'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import { matchScoreBand } from '@/lib/matchScore'

const STATUSES = ['', 'SUBMITTED', 'REVIEWING', 'SHORTLISTED', 'INTERVIEWING', 'HIRED', 'REJECTED', 'WITHDRAWN']

function ScoreBadge({ score, label }) {
  const band = matchScoreBand(score)
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span
        className={cn('inline-flex items-center justify-center px-2 py-1 rounded-full text-xs font-semibold border whitespace-nowrap', band.className)}
        title={score != null ? `Raw score: ${score}/100` : undefined}
      >
        {band.label}
      </span>
      {label && <span className="text-[10px] text-text-muted">{label}</span>}
    </div>
  )
}

function ScoreInfoTooltip({ text }) {
  const [visible, setVisible] = useState(false)
  return (
    <span className="relative inline-flex items-center ml-1">
      <button
        type="button"
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onFocus={() => setVisible(true)}
        onBlur={() => setVisible(false)}
        aria-label="Score explanation"
        className="text-text-muted hover:text-text-secondary transition-colors"
      >
        <Info size={13} />
      </button>
      {visible && (
        <div
          role="tooltip"
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-20 w-64 rounded-lg bg-gray-900 px-3 py-2 text-xs text-white shadow-lg pointer-events-none"
        >
          {text}
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
        </div>
      )}
    </span>
  )
}

// Expandable AI detail panel shown when a row is clicked
function AIDetailPanel({ app }) {
  if (!app.ai_fit_summary && !app.ai_strengths?.length && !app.ai_weaknesses?.length && !app.cover_letter) {
    return (
      <p className="text-xs text-text-muted italic py-2">No AI analysis available yet.</p>
    )
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
      {app.ai_fit_summary && (
        <div className="md:col-span-2">
          <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-1">AI Summary</p>
          <p className="text-text leading-relaxed">{app.ai_fit_summary}</p>
        </div>
      )}
      {app.ai_strengths?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-green-700 uppercase tracking-wide mb-1">Strengths</p>
          <ul className="space-y-1">
            {app.ai_strengths.map((s, i) => (
              <li key={i} className="flex gap-2 text-text-muted">
                <span className="text-green-500 mt-0.5 flex-shrink-0">✓</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {app.ai_weaknesses?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-red-600 uppercase tracking-wide mb-1">Gaps</p>
          <ul className="space-y-1">
            {app.ai_weaknesses.map((w, i) => (
              <li key={i} className="flex gap-2 text-text-muted">
                <span className="text-red-400 mt-0.5 flex-shrink-0">✗</span>
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {app.cover_letter && (
        <div className="md:col-span-2 border-t border-border pt-3">
          <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-1">Cover Letter</p>
          <p className="text-text-muted leading-relaxed whitespace-pre-wrap">{app.cover_letter}</p>
        </div>
      )}
    </div>
  )
}

export default function AdminApplicationsPage() {
  const { listApplications, getCvUrl, loading } = useAdmin()
  const { show, ToastContainer } = useToast()
  const [applications, setApplications] = useState([])
  const [cursor, setCursor] = useState(null)
  const [status, setStatus] = useState('')
  const [exporting, setExporting] = useState(false)
  const [expandedId, setExpandedId] = useState(null)

  const load = useCallback(async (reset = true) => {
    try {
      const params = { limit: 20 }
      if (status) params.status = status
      if (!reset && cursor) params.cursor = cursor
      const data = await listApplications(params)
      setApplications((prev) => reset ? (data.items ?? []) : [...prev, ...(data.items ?? [])])
      setCursor(data.next_cursor ?? null)
    } catch { /* handled by useAdmin */ }
  }, [status, cursor])

  useEffect(() => { load(true) }, [status])

  const handleCvDownload = async (cvId) => {
    try {
      const data = await getCvUrl(cvId)
      window.open(data.url, '_blank', 'noopener,noreferrer')
    } catch {
      show('Failed to get CV download link', 'error')
    }
  }

  const handleShortlist = async (appId, currentStatus) => {
    const newStatus = currentStatus === 'SHORTLISTED' ? 'REVIEWING' : 'SHORTLISTED'
    try {
      await api.patch(`/api/v1/applications/${appId}/status`, { new_status: newStatus })
      setApplications((prev) =>
        prev.map((a) => a.id === appId ? { ...a, status: newStatus } : a)
      )
      show(newStatus === 'SHORTLISTED' ? 'Candidate shortlisted' : 'Removed from shortlist')
    } catch {
      show('Failed to update shortlist', 'error')
    }
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const response = await api.get('/api/v1/admin/export/applications', { responseType: 'blob' })
      const url = URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = url
      a.download = 'applications.csv'
      a.click()
      URL.revokeObjectURL(url)
      show('CSV exported')
    } catch {
      show('Export failed', 'error')
    } finally {
      setExporting(false)
    }
  }

  const toggleExpand = (id) => setExpandedId((prev) => (prev === id ? null : id))

  return (
    <AdminLayout>
      <ToastContainer />

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-text">Applications</h1>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg border border-border hover:bg-surface-muted transition-colors disabled:opacity-50"
        >
          <Download size={14} aria-hidden="true" />
          {exporting ? 'Exporting…' : 'Export CSV'}
        </button>
      </div>

      <div className="mb-4">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue"
          aria-label="Filter by status"
        >
          {STATUSES.map((s) => <option key={s} value={s}>{s || 'All statuses'}</option>)}
        </select>
      </div>

      <AdminTable isEmpty={!loading && applications.length === 0} empty="No applications found.">
        <thead>
          <tr>
            <Th>Candidate</Th>
            <Th>Job</Th>
            <Th>Status</Th>
            <Th>Applied</Th>
            <Th>
              <span className="inline-flex items-center gap-0.5">
                Match
                <ScoreInfoTooltip text="Keyword-based match score: candidate skills vs job description." />
              </span>
            </Th>
            <Th>
              <span className="inline-flex items-center gap-0.5">
                AI Score
                <ScoreInfoTooltip text="Composite AI score combining skills analysis and LLM reasoning. Click a row to see the full breakdown." />
              </span>
            </Th>
            <Th>Shortlist</Th>
            <Th>CV</Th>
            <Th></Th>
          </tr>
        </thead>
        <tbody>
          {applications.map((a) => (
            <>
              <tr
                key={a.id}
                className="hover:bg-surface-muted/50 cursor-pointer"
                onClick={() => toggleExpand(a.id)}
              >
                <Td>
                  <div>
                    <p className="font-medium text-text">{a.candidate_name ?? ' - '}</p>
                    <p className="text-xs text-text-muted">{a.candidate_email ?? ''}</p>
                  </div>
                </Td>
                <Td className="text-text-muted">{a.job_title ?? ' - '}</Td>
                <Td><StatusBadge value={a.status} /></Td>
                <Td className="text-text-muted text-xs whitespace-nowrap">
                  {new Date(a.created_at ?? a.status_updated_at).toLocaleDateString()}
                </Td>
                <Td>
                  <ScoreBadge score={a.match_score} />
                </Td>
                <Td>
                  <ScoreBadge score={a.ai_score} />
                </Td>
                <Td>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleShortlist(a.id, a.status) }}
                    className={`p-1.5 rounded-lg transition-colors ${
                      a.status === 'SHORTLISTED'
                        ? 'text-yellow-500 hover:text-yellow-600'
                        : 'text-text-muted hover:text-yellow-500'
                    }`}
                    aria-label={a.status === 'SHORTLISTED' ? 'Remove from shortlist' : 'Shortlist candidate'}
                    title={a.status === 'SHORTLISTED' ? 'Remove from shortlist' : 'Add to shortlist'}
                  >
                    <Star size={15} fill={a.status === 'SHORTLISTED' ? 'currentColor' : 'none'} />
                  </button>
                </Td>
                <Td>
                  {a.cv_id ? (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleCvDownload(a.cv_id) }}
                      className="text-xs text-brand-blue hover:underline flex items-center gap-1"
                    >
                      <Download size={12} aria-hidden="true" />
                      Download
                    </button>
                  ) : (
                    <span className="text-xs text-text-muted"> - </span>
                  )}
                </Td>
                <Td>
                  {expandedId === a.id
                    ? <ChevronUp size={14} className="text-text-muted" />
                    : <ChevronDown size={14} className="text-text-muted" />
                  }
                </Td>
              </tr>

              {/* Expanded AI detail row */}
              {expandedId === a.id && (
                <tr key={`${a.id}-detail`}>
                  <td colSpan={9} className="bg-surface-muted/30 px-6 py-4 border-b border-border">
                    <AIDetailPanel app={a} />
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </AdminTable>

      <Pagination cursor={cursor} onLoadMore={() => load(false)} loading={loading} />
    </AdminLayout>
  )
}
