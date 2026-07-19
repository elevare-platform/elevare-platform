import { useEffect, useState, useCallback } from 'react'
import { FileText } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'
import { AdminTable, Th, Td, Pagination } from '@/components/admin/AdminTable'
import StatusBadge from '@/components/admin/StatusBadge'
import ConfirmModal from '@/components/admin/ConfirmModal'
import { useToast } from '@/components/admin/Toast'
import { useAdmin } from '@/hooks/useAdmin'

const KYC_STATUSES = ['', 'NOT_SUBMITTED', 'PENDING', 'APPROVED', 'REJECTED']

export default function AdminKycPage() {
  const { listKycSubmissions, moderateKyc, getKycDocumentUrl, loading } = useAdmin()
  const { show, ToastContainer } = useToast()
  const [submissions, setSubmissions] = useState([])
  const [cursor, setCursor] = useState(null)
  const [statusFilter, setStatusFilter] = useState('PENDING')
  const [confirm, setConfirm] = useState(null)

  const load = useCallback(async (reset = true) => {
    try {
      const params = { limit: 20 }
      if (statusFilter) params.status = statusFilter
      if (!reset && cursor) params.cursor = cursor
      const data = await listKycSubmissions(params)
      setSubmissions((prev) => reset ? (data.items ?? []) : [...prev, ...(data.items ?? [])])
      setCursor(data.next_cursor ?? null)
    } catch { /* handled */ }
  }, [statusFilter, cursor])

  useEffect(() => { load(true) }, [statusFilter])

  const handleModerate = async (employerProfileId, action, reason = null) => {
    try {
      await moderateKyc(employerProfileId, action, reason)
      show(`KYC ${action === 'APPROVED' ? 'approved' : 'rejected'} successfully`)
      load(true)
    } catch {
      show('Moderation action failed', 'error')
    }
    setConfirm(null)
  }

  const handleViewDocument = async (documentId) => {
    try {
      const url = await getKycDocumentUrl(documentId)
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch {
      show('Could not open document', 'error')
    }
  }

  return (
    <AdminLayout>
      <ToastContainer />

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
        <h1 className="text-2xl font-bold text-text">Company Verification (KYC)</h1>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
          className="text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue"
          aria-label="Filter by KYC status">
          {KYC_STATUSES.map((s) => <option key={s} value={s}>{s || 'All statuses'}</option>)}
        </select>
      </div>

      <AdminTable isEmpty={!loading && submissions.length === 0} empty="No KYC submissions found.">
        <thead>
          <tr>
            <Th>Company</Th>
            <Th>Contact</Th>
            <Th>Status</Th>
            <Th>Documents</Th>
            <Th>Submitted</Th>
            <Th>Actions</Th>
          </tr>
        </thead>
        <tbody>
          {submissions.map((s) => (
            <tr key={s.employer_profile_id} className="hover:bg-surface-muted/50">
              <Td className="font-medium text-text">{s.company_name ?? '—'}</Td>
              <Td className="text-text-muted">
                <div>{s.first_name} {s.last_name}</div>
                <div className="text-xs">{s.email}</div>
              </Td>
              <Td>
                <StatusBadge value={s.kyc_status} />
                {s.kyc_status === 'REJECTED' && s.kyc_rejection_reason && (
                  <p className="text-xs text-red-600 mt-1 max-w-56">{s.kyc_rejection_reason}</p>
                )}
              </Td>
              <Td>
                <div className="flex flex-col gap-1">
                  {s.documents.length === 0 && <span className="text-xs text-text-muted">None</span>}
                  {s.documents.map((doc) => (
                    <button
                      key={doc.id}
                      onClick={() => handleViewDocument(doc.id)}
                      className="flex items-center gap-1 text-xs text-brand-blue hover:underline text-left"
                    >
                      <FileText size={12} aria-hidden="true" />
                      {doc.document_type}
                    </button>
                  ))}
                </div>
              </Td>
              <Td className="text-text-muted text-xs">
                {s.kyc_submitted_at ? new Date(s.kyc_submitted_at).toLocaleDateString() : '—'}
              </Td>
              <Td>
                {s.kyc_status === 'PENDING' && (
                  <div className="flex gap-2">
                    <button
                      onClick={() => setConfirm({
                        label: `Approve ${s.company_name ?? 'this company'}?`,
                        confirmLabel: 'Approve',
                        danger: false,
                        onConfirm: () => handleModerate(s.employer_profile_id, 'APPROVED'),
                      })}
                      className="text-xs text-green-700 hover:underline">
                      Approve
                    </button>
                    <button
                      onClick={() => setConfirm({
                        label: `Reject ${s.company_name ?? 'this company'}?`,
                        confirmLabel: 'Reject',
                        danger: true,
                        isReject: true,
                        onConfirm: (reason) => handleModerate(s.employer_profile_id, 'REJECTED', reason),
                      })}
                      className="text-xs text-red-600 hover:underline">
                      Reject
                    </button>
                  </div>
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
