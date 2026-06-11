import { useEffect, useState, useCallback } from 'react'
import { Download, Star, Info } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'
import { AdminTable, Th, Td, Pagination } from '@/components/admin/AdminTable'
import StatusBadge from '@/components/admin/StatusBadge'
import { useToast } from '@/components/admin/Toast'
import { useAdmin } from '@/hooks/useAdmin'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

const STATUSES = ['', 'SUBMITTED', 'REVIEWING', 'SHORTLISTED', 'HIRED', 'REJECTED', 'WITHDRAWN']

function scoreColour(score) {
  if (score === null || score === undefined) return 'bg-gray-100 text-gray-500'
  if (score <= 40) return 'bg-red-100 text-[#DC2626]'
  if (score <= 70) return 'bg-amber-100 text-[#E87722]'
  return 'bg-green-100 text-[#16A34A]'
}

function MatchScoreBadge({ score }) {
  const hasScore = score !== null && score !== undefined
  return (
    <span className={cn(
      'inline-flex items-center justify-center w-10 h-10 rounded-full text-sm font-semibold',
      scoreColour(score)
    )}>
      {hasScore ? `${score}%` : '—'}
    </span>
  )
}

function ScoreInfoTooltip() {
  const [visible, setVisible] = useState(false)
  return (
    <span className="relative inline-flex items-center ml-1">
      <button
        type="button"
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onFocus={() => setVisible(true)}
        onBlur={() => setVisible(false)}
        aria-label="Match score explanation"
        className="text-text-muted hover:text-text-secondary transition-colors"
      >
        <Info size={13} />
      </button>
      {visible && (
        <div
          role="tooltip"
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-20 w-56 rounded-lg bg-gray-900 px-3 py-2 text-xs text-white shadow-lg pointer-events-none"
        >
          Score based on candidate skills vs job description keywords. Higher is better.
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
        </div>
      )}
    </span>
  )
}

export default function AdminApplicationsPage() {
  const { listApplications, getCvUrl, loading } = useAdmin()
  const { show, ToastContainer } = useToast()
  const [applications, setApplications] = useState([])
  const [cursor, setCursor] = useState(null)
  const [status, setStatus] = useState('')
  const [exporting, setExporting] = useState(false)

  const load = useCallback(async (reset = true) => {
    try {
      const params = { limit: 20 }
      if (status) params.status = status
      if (!reset && cursor) params.cursor = cursor
      const data = await listApplications(params)
      setApplications((prev) => reset ? (data.items ?? []) : [...prev, ...(data.items ?? [])])
      setCursor(data.next_cursor ?? null)
    } catch { /* handled */ }
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
      await api.patch(`/api/v1/applications/${appId}/status`, { status: newStatus })
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
        <select value={status} onChange={(e) => setStatus(e.target.value)}
          className="text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue"
          aria-label="Filter by status">
          {STATUSES.map((s) => <option key={s} value={s}>{s || 'All statuses'}</option>)}
        </select>
      </div>

      <AdminTable isEmpty={!loading && applications.length === 0} empty="No applications found.">
        <thead>
          <tr>
            <Th>Candidate</Th>
            <Th>Job</Th>
            <Th>Company</Th>
            <Th>Status</Th>
            <Th>Applied</Th>
            <Th>
              <span className="inline-flex items-center gap-0.5">
                Match Score
                <ScoreInfoTooltip />
              </span>
            </Th>
            <Th>Shortlist</Th>
            <Th>CV</Th>
          </tr>
        </thead>
        <tbody>
          {applications.map((a) => (
            <tr key={a.id} className="hover:bg-surface-muted/50">
              <Td>
                <div>
                  <p className="font-medium">{a.candidate?.first_name} {a.candidate?.last_name}</p>
                  <p className="text-xs text-text-muted">{a.candidate?.email}</p>
                  {/* Matched keyword chips */}
                  {a.matched_keywords?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {a.matched_keywords.map((kw) => (
                        <span
                          key={kw}
                          className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-brand-blue/10 text-brand-blue"
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </Td>
              <Td className="text-text-muted">{a.job?.title ?? a.job_title ?? '—'}</Td>
              <Td className="text-text-muted">
                {a.job?.employer?.employer_profile?.company_name ?? a.company_name ?? '—'}
              </Td>
              <Td><StatusBadge value={a.status} /></Td>
              <Td className="text-text-muted text-xs">
                {new Date(a.status_updated_at ?? a.created_at).toLocaleDateString()}
              </Td>
              <Td>
                <MatchScoreBadge score={a.match_score} />
              </Td>
              <Td>
                <button
                  onClick={() => handleShortlist(a.id, a.status)}
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
                    onClick={() => handleCvDownload(a.cv_id)}
                    className="text-xs text-brand-blue hover:underline flex items-center gap-1"
                  >
                    <Download size={12} aria-hidden="true" />
                    Download
                  </button>
                ) : (
                  <span className="text-xs text-text-muted">—</span>
                )}
              </Td>
            </tr>
          ))}
        </tbody>
      </AdminTable>

      <Pagination cursor={cursor} onLoadMore={() => load(false)} loading={loading} />
    </AdminLayout>
  )
}
