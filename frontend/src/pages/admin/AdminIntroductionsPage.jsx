import { useEffect, useState, useCallback } from 'react'
import { Send, CheckCircle2, XCircle, Clock } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'
import { AdminTable, Th, Td } from '@/components/admin/AdminTable'
import { useToast } from '@/components/admin/Toast'
import { useAdmin } from '@/hooks/useAdmin'
import { cn } from '@/lib/utils'

/**
 * AdminIntroductionsPage — ops queue for admin-sourced talent profiles.
 *
 * When an employer requests an introduction to a profile an admin sourced
 * (talent_pool_profiles.added_by == an admin), the request routes here
 * instead of an automated candidate email. The admin does the outreach
 * off-platform, then Accept/Decline reflects the real answer.
 *
 * Expected GET /api/v1/admin/introductions?assigned_to=me&status=... shape
 * per row: id, job_id, job_title, talent_pool_profile_id, candidate_name,
 * candidate_current_title, employer_name, employer_email, status,
 * created_at, expires_at, responded_at.
 * See docs/talent-pool-isolation-and-introduction-routing.md (Phase 5).
 */

const STATUS_STYLES = {
  PENDING: { icon: Clock, label: 'Pending', className: 'bg-amber-50 text-amber-700 border-amber-200' },
  ACCEPTED: { icon: CheckCircle2, label: 'Accepted', className: 'bg-green-50 text-green-700 border-green-200' },
  DECLINED: { icon: XCircle, label: 'Declined', className: 'bg-gray-100 text-gray-500 border-gray-200' },
  EXPIRED: { icon: Clock, label: 'Expired', className: 'bg-gray-100 text-gray-500 border-gray-200' },
}

const FILTER_TABS = ['all', 'PENDING', 'ACCEPTED', 'DECLINED', 'EXPIRED']

function formatDate(isoString) {
  if (!isoString) return '—'
  return new Date(isoString).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function StatusBadge({ status }) {
  const config = STATUS_STYLES[status] ?? STATUS_STYLES.PENDING
  const Icon = config.icon
  return (
    <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border', config.className)}>
      <Icon size={12} />
      {config.label}
    </span>
  )
}

export default function AdminIntroductionsPage() {
  const { listAssignedIntroductions, acceptIntroduction, declineIntroduction, loading } = useAdmin()
  const { show, ToastContainer } = useToast()
  const [items, setItems] = useState([])
  const [activeTab, setActiveTab] = useState('all')
  const [actingOn, setActingOn] = useState(null) // id currently being accepted/declined

  const load = useCallback(async () => {
    try {
      const params = { assigned_to: 'me' }
      if (activeTab !== 'all') params.status = activeTab
      const data = await listAssignedIntroductions(params)
      setItems(Array.isArray(data) ? data : data.items ?? [])
    } catch {
      // handled via hook's error state; keep prior list on screen
    }
  }, [activeTab])

  useEffect(() => { load() }, [load])

  const handleAccept = async (id) => {
    setActingOn(id)
    try {
      await acceptIntroduction(id)
      setItems((prev) => prev.map((i) => i.id === id ? { ...i, status: 'ACCEPTED' } : i))
      show('Marked as accepted — the employer can now view this profile.')
    } catch {
      show('Failed to accept. Please try again.', 'error')
    } finally {
      setActingOn(null)
    }
  }

  const handleDecline = async (id) => {
    setActingOn(id)
    try {
      await declineIntroduction(id)
      setItems((prev) => prev.map((i) => i.id === id ? { ...i, status: 'DECLINED' } : i))
      show('Marked as declined — the employer\'s credit was refunded.')
    } catch {
      show('Failed to decline. Please try again.', 'error')
    } finally {
      setActingOn(null)
    }
  }

  return (
    <AdminLayout>
      <ToastContainer />

      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-bold text-text flex items-center gap-2">
          <Send size={22} className="text-brand-blue" />
          Introduction Requests
        </h1>
      </div>
      <p className="text-sm text-text-muted mb-6">
        Employer requests for profiles you sourced. Reach out to the candidate off-platform,
        then reflect their answer here.
      </p>

      <div className="flex flex-wrap gap-1.5 mb-4" role="tablist" aria-label="Filter by status">
        {FILTER_TABS.map((tab) => (
          <button
            key={tab}
            role="tab"
            aria-selected={activeTab === tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              'px-3 py-1.5 rounded-full text-xs font-medium capitalize transition-colors',
              activeTab === tab ? 'bg-brand-blue text-white' : 'bg-white border border-border text-text-muted hover:text-text'
            )}
          >
            {tab === 'all' ? 'All' : STATUS_STYLES[tab].label}
          </button>
        ))}
      </div>

      <AdminTable isEmpty={!loading && items.length === 0} empty="No introduction requests here.">
        <thead>
          <tr>
            <Th>Candidate</Th>
            <Th>Employer</Th>
            <Th>Job</Th>
            <Th>Requested</Th>
            <Th>Status</Th>
            <Th>Actions</Th>
          </tr>
        </thead>
        <tbody>
          {items.map((i) => (
            <tr key={i.id} className="hover:bg-surface-muted/50">
              <Td>
                <p className="font-medium text-text">{i.candidate_name ?? 'Unnamed candidate'}</p>
                {i.candidate_current_title && <p className="text-xs text-text-muted">{i.candidate_current_title}</p>}
              </Td>
              <Td className="text-text-muted">
                <p>{i.employer_name ?? '—'}</p>
                {i.employer_email && <p className="text-xs">{i.employer_email}</p>}
              </Td>
              <Td className="text-text-muted">{i.job_title}</Td>
              <Td className="text-text-muted text-xs">{formatDate(i.created_at)}</Td>
              <Td><StatusBadge status={i.status} /></Td>
              <Td>
                {i.status === 'PENDING' ? (
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleAccept(i.id)}
                      disabled={actingOn === i.id}
                      className="text-xs text-green-700 hover:underline disabled:opacity-50"
                    >
                      Accept
                    </button>
                    <button
                      onClick={() => handleDecline(i.id)}
                      disabled={actingOn === i.id}
                      className="text-xs text-red-600 hover:underline disabled:opacity-50"
                    >
                      Decline
                    </button>
                  </div>
                ) : (
                  <span className="text-xs text-text-muted">
                    {i.responded_at ? `Resolved ${formatDate(i.responded_at)}` : '—'}
                  </span>
                )}
              </Td>
            </tr>
          ))}
        </tbody>
      </AdminTable>
    </AdminLayout>
  )
}
