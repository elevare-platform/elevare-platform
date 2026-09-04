import { useEffect, useState, useCallback } from 'react'
import AdminLayout from '@/components/admin/AdminLayout'
import { AdminTable, Th, Td } from '@/components/admin/AdminTable'
import StatusBadge from '@/components/admin/StatusBadge'
import ConfirmModal from '@/components/admin/ConfirmModal'
import TestimonialDetailDrawer from '@/components/admin/TestimonialDetailDrawer'
import { useToast } from '@/components/admin/Toast'
import { useAdmin } from '@/hooks/useAdmin'

const STATUS_FILTERS = ['', 'pending', 'approved', 'rejected']

const CONFIRM_COPY = {
  approved: { label: 'Approve this testimonial?', confirmLabel: 'Approve', danger: false },
  rejected: {
    label: 'Reject this testimonial?',
    description: 'The submitter will not be notified.',
    confirmLabel: 'Reject',
    danger: true,
  },
  pending: { label: 'Reset to pending?', confirmLabel: 'Reset', danger: false },
}

export default function AdminTestimonialsPage() {
  const { listTestimonials, moderateTestimonial, loading } = useAdmin()
  const { show, ToastContainer } = useToast()
  const [testimonials, setTestimonials] = useState([])
  const [statusFilter, setStatusFilter] = useState('')
  const [confirm, setConfirm] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const selectedTestimonial = testimonials.find((t) => t.id === selectedId) ?? null

  const load = useCallback(async () => {
    try {
      const params = {}
      if (statusFilter) params.status = statusFilter
      const data = await listTestimonials(params)
      setTestimonials(data)
    } catch { /* handled by hook */ }
  }, [statusFilter])

  useEffect(() => { load() }, [load])

  const handleModerate = async (id, status) => {
    try {
      await moderateTestimonial(id, status)
      show(`Testimonial ${status}`)
      load()
    } catch {
      show('Action failed', 'error')
    }
    setConfirm(null)
  }

  const requestModerate = (t, status) => {
    setConfirm({ ...CONFIRM_COPY[status], onConfirm: () => handleModerate(t.id, status) })
  }

  return (
    <AdminLayout>
      <ToastContainer />

      {selectedTestimonial && (
        <TestimonialDetailDrawer
          testimonial={selectedTestimonial}
          onClose={() => setSelectedId(null)}
          onRequestModerate={requestModerate}
        />
      )}

      {confirm && (
        <ConfirmModal
          title={confirm.label}
          description={confirm.description ?? 'This action can be undone by changing the status again.'}
          confirmLabel={confirm.confirmLabel}
          danger={confirm.danger}
          onConfirm={() => confirm.onConfirm()}
          onCancel={() => setConfirm(null)}
        />
      )}

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-text">Testimonials</h1>
      </div>

      {/* Filter */}
      <div className="flex gap-3 mb-4">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue"
          aria-label="Filter by status"
        >
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>{s ? s.charAt(0).toUpperCase() + s.slice(1) : 'All statuses'}</option>
          ))}
        </select>
      </div>

      <AdminTable isEmpty={!loading && testimonials.length === 0} empty="No testimonials found.">
        <thead>
          <tr>
            <Th>Name</Th>
            <Th>Company / Position</Th>
            <Th>Testimony</Th>
            <Th>Status</Th>
            <Th>Submitted</Th>
            <Th>Actions</Th>
          </tr>
        </thead>
        <tbody>
          {testimonials.map((t) => (
            <tr key={t.id} className="hover:bg-surface-muted/50">
              <Td>
                <button
                  onClick={() => setSelectedId(t.id)}
                  className="flex items-center gap-3 text-left"
                >
                  {t.image_url ? (
                    <img src={t.image_url} alt={t.full_name} className="w-8 h-8 rounded-full object-cover flex-shrink-0" />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-brand-blue-light text-brand-blue flex items-center justify-center text-sm font-bold flex-shrink-0">
                      {t.full_name.charAt(0)}
                    </div>
                  )}
                  <span className="font-medium text-brand-blue hover:underline">{t.full_name}</span>
                </button>
              </Td>
              <Td className="text-text-muted text-xs">
                {[t.position, t.company].filter(Boolean).join(', ') || ' - '}
              </Td>
              <Td>
                <p className="text-sm text-text max-w-xs truncate" title={t.testimony}>
                  {t.testimony}
                </p>
              </Td>
              <Td><StatusBadge value={t.status} /></Td>
              <Td className="text-text-muted text-xs">{new Date(t.created_at).toLocaleDateString()}</Td>
              <Td>
                <div className="flex gap-2">
                  <button
                    onClick={() => setSelectedId(t.id)}
                    className="text-xs text-text-muted hover:text-brand-blue hover:underline"
                  >
                    View
                  </button>
                  {t.status !== 'approved' && (
                    <button
                      onClick={() => requestModerate(t, 'approved')}
                      className="text-xs text-green-700 hover:underline"
                    >
                      Approve
                    </button>
                  )}
                  {t.status !== 'rejected' && (
                    <button
                      onClick={() => requestModerate(t, 'rejected')}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Reject
                    </button>
                  )}
                  {t.status !== 'pending' && (
                    <button
                      onClick={() => requestModerate(t, 'pending')}
                      className="text-xs text-text-muted hover:underline"
                    >
                      Reset
                    </button>
                  )}
                </div>
              </Td>
            </tr>
          ))}
        </tbody>
      </AdminTable>
    </AdminLayout>
  )
}
