import { useEffect, useState, useCallback } from 'react'
import { Search } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'
import { AdminTable, Th, Td, Pagination } from '@/components/admin/AdminTable'
import StatusBadge from '@/components/admin/StatusBadge'
import JobDetailDrawer from '@/components/admin/JobDetailDrawer'
import ConfirmModal from '@/components/admin/ConfirmModal'
import { useToast } from '@/components/admin/Toast'
import { useAdmin } from '@/hooks/useAdmin'

const MODERATION_STATUSES = ['', 'PENDING', 'APPROVED', 'REJECTED']
const JOB_STATUSES = ['', 'DRAFT', 'ACTIVE', 'CLOSED']

export default function AdminJobsPage() {
  const { listJobs, moderateJob, bulkUpdateJobs, loading } = useAdmin()
  const { show, ToastContainer } = useToast()
  const [jobs, setJobs] = useState([])
  const [cursor, setCursor] = useState(null)
  const [search, setSearch] = useState('')
  const [moderationFilter, setModerationFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selected, setSelected] = useState([])
  const [drawerJobId, setDrawerJobId] = useState(null)
  const [confirm, setConfirm] = useState(null)

  const load = useCallback(async (reset = true) => {
    try {
      const params = { limit: 20 }
      if (search) params.search = search
      if (moderationFilter) params.moderation_status = moderationFilter
      if (statusFilter) params.status = statusFilter
      if (!reset && cursor) params.cursor = cursor
      const data = await listJobs(params)
      setJobs((prev) => reset ? (data.items ?? []) : [...prev, ...(data.items ?? [])])
      setCursor(data.next_cursor ?? null)
      if (reset) setSelected([])
    } catch { /* handled */ }
  }, [search, moderationFilter, statusFilter, cursor])

  useEffect(() => { load(true) }, [search, moderationFilter, statusFilter])

  const handleModerate = async (jobId, action, reason = null) => {
    try {
      await moderateJob(jobId, action, reason)
      show(`Job ${action.toLowerCase()}d successfully`)
      load(true)
    } catch {
      show('Moderation action failed', 'error')
    }
    setConfirm(null)
  }

  const handleBulk = async (action) => {
    if (!selected.length) return
    try {
      await bulkUpdateJobs(selected, action)
      show(`${selected.length} jobs updated`)
      load(true)
      setSelected([])
    } catch {
      show('Bulk update failed', 'error')
    }
    setConfirm(null)
  }

  const toggleSelect = (id) =>
    setSelected((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])

  const toggleAll = () =>
    setSelected(selected.length === jobs.length ? [] : jobs.map((j) => j.id))

  return (
    <AdminLayout>
      <ToastContainer />

      {drawerJobId && (
        <JobDetailDrawer
          jobId={drawerJobId}
          onClose={() => setDrawerJobId(null)}
          onModerate={() => { load(true); show('Job moderation updated') }}
        />
      )}

      {confirm && (
        <ConfirmModal
          title={confirm.label}
          description="This action will be recorded in the audit log."
          confirmLabel={confirm.confirmLabel}
          danger={confirm.danger}
          requireReason={confirm.isReject}
          onConfirm={(reason) => confirm.onConfirm(reason)}
          onCancel={() => setConfirm(null)}
        />
      )}

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-text">Jobs</h1>
        {selected.length > 0 && (
          <button
            onClick={() => setConfirm({
              label: `Close ${selected.length} jobs?`,
              confirmLabel: 'Close Jobs',
              danger: true,
              onConfirm: () => handleBulk('CLOSED'),
            })}
            className="px-3 py-1.5 text-sm rounded-lg bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
          >
            Close ({selected.length})
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" aria-hidden="true" />
          <input type="search" placeholder="Search title or location…" value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-2 text-sm rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-brand-blue"
            aria-label="Search jobs" />
        </div>
        <select value={moderationFilter} onChange={(e) => setModerationFilter(e.target.value)}
          className="text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue"
          aria-label="Filter by moderation status">
          {MODERATION_STATUSES.map((s) => <option key={s} value={s}>{s || 'All moderation'}</option>)}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
          className="text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue"
          aria-label="Filter by job status">
          {JOB_STATUSES.map((s) => <option key={s} value={s}>{s || 'All statuses'}</option>)}
        </select>
      </div>

      <AdminTable isEmpty={!loading && jobs.length === 0} empty="No jobs found.">
        <thead>
          <tr>
            <Th>
              <input type="checkbox"
                checked={selected.length === jobs.length && jobs.length > 0}
                onChange={toggleAll} aria-label="Select all jobs" />
            </Th>
            <Th>Title</Th>
            <Th>Company</Th>
            <Th>Status</Th>
            <Th>Moderation</Th>
            <Th>Posted</Th>
            <Th>Actions</Th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr key={j.id} className="hover:bg-surface-muted/50">
              <Td>
                <input type="checkbox" checked={selected.includes(j.id)}
                  onChange={() => toggleSelect(j.id)} aria-label={`Select ${j.title}`} />
              </Td>
              <Td>
                <button
                  onClick={() => setDrawerJobId(j.id)}
                  className="font-medium text-brand-blue hover:underline text-left"
                >
                  {j.title}
                </button>
              </Td>
              <Td className="text-text-muted">
                {j.employer?.employer_profile?.company_name ?? '—'}
              </Td>
              <Td><StatusBadge value={j.status} /></Td>
              <Td><StatusBadge value={j.moderation_status} /></Td>
              <Td className="text-text-muted text-xs">{new Date(j.created_at).toLocaleDateString()}</Td>
              <Td>
                <div className="flex gap-2">
                  <button onClick={() => setDrawerJobId(j.id)}
                    className="text-xs text-text-muted hover:text-brand-blue hover:underline">
                    View
                  </button>
                  {j.moderation_status === 'PENDING' && (
                    <>
                      <button
                        onClick={() => setConfirm({
                          label: 'Approve this job?',
                          confirmLabel: 'Approve',
                          danger: false,
                          onConfirm: () => handleModerate(j.id, 'APPROVED'),
                        })}
                        className="text-xs text-green-700 hover:underline">
                        Approve
                      </button>
                      <button
                        onClick={() => setConfirm({
                          label: 'Reject this job?',
                          confirmLabel: 'Reject',
                          danger: true,
                          isReject: true,
                          onConfirm: (reason) => handleModerate(j.id, 'REJECTED', reason),
                        })}
                        className="text-xs text-red-600 hover:underline">
                        Reject
                      </button>
                    </>
                  )}
                  {j.status === 'ACTIVE' && (
                    <button
                      onClick={() => setConfirm({
                        label: 'Close this job?',
                        confirmLabel: 'Close',
                        danger: true,
                        onConfirm: () => handleModerate(j.id, 'close'),
                      })}
                      className="text-xs text-text-muted hover:underline">
                      Close
                    </button>
                  )}
                </div>
              </Td>
            </tr>
          ))}
        </tbody>
      </AdminTable>

      <Pagination cursor={cursor} onLoadMore={() => load(false)} loading={loading} />
    </AdminLayout>
  )
}
