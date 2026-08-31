import { useEffect, useState, useCallback, useMemo } from 'react'
import { Send, CheckCircle2, XCircle, Clock, FileText } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'
import { Th, Td } from '@/components/admin/AdminTable'
import { useToast } from '@/components/admin/Toast'
import { useAdmin } from '@/hooks/useAdmin'
import SourcedCvModal from '@/components/employer/SourcedCvModal'
import { cn } from '@/lib/utils'

/**
 * AdminIntroductionsPage - ops queue for admin-sourced talent profiles.
 *
 * When an employer requests an introduction to a profile an admin sourced
 * (talent_pool_profiles.added_by == an admin), the request routes here
 * instead of an automated candidate email. The admin does the outreach
 * off-platform, then Accept/Decline reflects the real answer.
 *
 * Requests are grouped by employer, not shown as one flat chronological
 * list - a second request from an employer who already has one pending
 * belongs next to their first, not buried between unrelated employers'
 * requests. Each request also links straight to the candidate's CV so the
 * admin can actually do the off-platform outreach (and verify consent)
 * from this screen, without hunting for contact details elsewhere.
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
  if (!isoString) return ' - '
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

// Groups requests by employer (falling back to employer_id if email/name
// are both missing), each group sorted newest-first internally, and groups
// themselves ordered by their most recent request - an employer who just
// made a new request surfaces above one who's been quiet for a while.
function groupByEmployer(items) {
  const groups = new Map()
  for (const item of items) {
    const key = item.employer_email ?? item.employer_name ?? 'unknown'
    if (!groups.has(key)) {
      groups.set(key, {
        employer_name: item.employer_name,
        employer_email: item.employer_email,
        requests: [],
      })
    }
    groups.get(key).requests.push(item)
  }

  const result = Array.from(groups.values())
  for (const group of result) {
    group.requests.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  }
  result.sort(
    (a, b) => new Date(b.requests[0].created_at) - new Date(a.requests[0].created_at)
  )
  return result
}

export default function AdminIntroductionsPage() {
  const { listAssignedIntroductions, acceptIntroduction, declineIntroduction, loading } = useAdmin()
  const { show, ToastContainer } = useToast()
  const [items, setItems] = useState([])
  const [activeTab, setActiveTab] = useState('all')
  const [actingOn, setActingOn] = useState(null) // id currently being accepted/declined
  const [cvProfileId, setCvProfileId] = useState(null)

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

  const groups = useMemo(() => groupByEmployer(items), [items])

  const handleAccept = async (id) => {
    setActingOn(id)
    try {
      await acceptIntroduction(id)
      setItems((prev) => prev.map((i) => i.id === id ? { ...i, status: 'ACCEPTED' } : i))
      show('Marked as accepted - the employer can now view this profile.')
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
      show('Marked as declined - the employer\'s credit was refunded.')
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
        Employer requests for profiles you sourced, grouped by employer. Open the CV to reach
        out to the candidate off-platform and confirm they're willing to be introduced, then
        reflect their answer here.
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

      {!loading && groups.length === 0 && (
        <div className="rounded-xl border border-dashed border-border bg-white p-10 text-center text-sm text-text-muted">
          No introduction requests here.
        </div>
      )}

      <div className="space-y-6">
        {groups.map((group) => (
          <div key={group.employer_email ?? group.employer_name} className="rounded-xl border border-border bg-white overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 bg-surface-muted border-b border-border">
              <div>
                <p className="text-sm font-semibold text-text">{group.employer_name ?? 'Unknown employer'}</p>
                {group.employer_email && <p className="text-xs text-text-muted">{group.employer_email}</p>}
              </div>
              <span className="text-xs text-text-muted">
                {group.requests.length} request{group.requests.length > 1 ? 's' : ''}
              </span>
            </div>

            <table className="w-full text-sm">
              <thead className="sr-only">
                <tr>
                  <Th>Candidate</Th>
                  <Th>Job</Th>
                  <Th>Requested</Th>
                  <Th>Status</Th>
                  <Th>Actions</Th>
                </tr>
              </thead>
              <tbody>
                {group.requests.map((i) => (
                  <tr key={i.id} className="border-b border-border last:border-0 hover:bg-surface-muted/50">
                    <Td>
                      <div className="flex items-center gap-2">
                        <div>
                          <p className="font-medium text-text">{i.candidate_name ?? 'Unnamed candidate'}</p>
                          {i.candidate_current_title && <p className="text-xs text-text-muted">{i.candidate_current_title}</p>}
                        </div>
                        <button
                          type="button"
                          onClick={() => setCvProfileId(i.talent_pool_profile_id)}
                          className="inline-flex items-center gap-1 text-xs text-brand-blue hover:underline flex-shrink-0"
                        >
                          <FileText size={12} /> View CV
                        </button>
                      </div>
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
                          {i.responded_at ? `Resolved ${formatDate(i.responded_at)}` : ' - '}
                        </span>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>

      {cvProfileId && (
        <SourcedCvModal profileId={cvProfileId} onClose={() => setCvProfileId(null)} />
      )}
    </AdminLayout>
  )
}
