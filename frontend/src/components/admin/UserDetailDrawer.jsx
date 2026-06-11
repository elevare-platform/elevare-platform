import { useEffect, useState } from 'react'
import { X, Mail, Phone, Calendar, Shield } from 'lucide-react'
import StatusBadge from './StatusBadge'
import api from '@/lib/api'

const STATUSES = ['ACTIVE', 'SUSPENDED', 'DEACTIVATED', 'BANNED']

export default function UserDetailDrawer({ userId, onClose, onStatusChange }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!userId) return
    setLoading(true)
    api.get(`/api/v1/admin/users/${userId}`)
      .then((r) => setUser(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [userId])

  const handleStatusChange = async (newStatus) => {
    try {
      await api.patch(`/api/v1/admin/users/${userId}`, { status: newStatus })
      setUser((prev) => ({ ...prev, account_status: newStatus }))
      onStatusChange?.(userId, newStatus)
    } catch { /* silently fail */ }
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <aside
        className="relative z-50 w-full max-w-md bg-white h-full shadow-xl flex flex-col overflow-y-auto"
        role="dialog"
        aria-label="User details"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="font-semibold text-text">User Details</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-surface-muted" aria-label="Close">
            <X size={16} />
          </button>
        </div>

        {loading && (
          <div className="flex-1 flex items-center justify-center">
            <div className="w-6 h-6 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!loading && user && (
          <div className="flex-1 px-6 py-5 space-y-6">
            {/* Identity */}
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-full bg-brand-blue/10 flex items-center justify-center text-brand-blue font-bold text-lg flex-shrink-0">
                {user.first_name?.[0]}{user.last_name?.[0]}
              </div>
              <div>
                <p className="font-semibold text-text text-lg">{user.first_name} {user.last_name}</p>
                <div className="flex gap-2 mt-1">
                  <StatusBadge value={user.role} />
                  <StatusBadge value={user.account_status} />
                </div>
              </div>
            </div>

            {/* Details */}
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-sm">
                <Mail size={14} className="text-text-muted flex-shrink-0" />
                <span className="text-text">{user.email}</span>
              </div>
              {user.phone_number && (
                <div className="flex items-center gap-3 text-sm">
                  <Phone size={14} className="text-text-muted flex-shrink-0" />
                  <span className="text-text">{user.phone_number}</span>
                </div>
              )}
              <div className="flex items-center gap-3 text-sm">
                <Calendar size={14} className="text-text-muted flex-shrink-0" />
                <span className="text-text-muted">
                  Joined {new Date(user.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}
                </span>
              </div>
              {user.last_login_at && (
                <div className="flex items-center gap-3 text-sm">
                  <Shield size={14} className="text-text-muted flex-shrink-0" />
                  <span className="text-text-muted">
                    Last login {new Date(user.last_login_at).toLocaleDateString()}
                  </span>
                </div>
              )}
            </div>

            {/* Employer profile */}
            {user.employer_profile && (
              <div className="rounded-xl border border-border p-4 space-y-2">
                <p className="text-xs font-semibold text-text-muted uppercase tracking-wider">Company</p>
                <p className="font-medium text-text">{user.employer_profile.company_name ?? '—'}</p>
                <div className="flex gap-3 text-xs text-text-muted">
                  {user.employer_profile.industry && <span>{user.employer_profile.industry}</span>}
                  {user.employer_profile.company_size && <span>{user.employer_profile.company_size} employees</span>}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-text-muted">Profile complete:</span>
                  <StatusBadge value={user.employer_profile.is_profile_complete ? 'ACTIVE' : 'PENDING'} />
                </div>
              </div>
            )}

            {/* Candidate profile */}
            {user.candidate_profile && (
              <div className="rounded-xl border border-border p-4 space-y-2">
                <p className="text-xs font-semibold text-text-muted uppercase tracking-wider">Candidate Profile</p>
                {user.candidate_profile.current_title && (
                  <p className="text-sm text-text">{user.candidate_profile.current_title}</p>
                )}
                {user.candidate_profile.years_of_experience != null && (
                  <p className="text-xs text-text-muted">{user.candidate_profile.years_of_experience} years experience</p>
                )}
              </div>
            )}

            {/* Status control — not shown for admins */}
            {user.role !== 'ADMIN' && (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-text-muted uppercase tracking-wider">Change Status</p>
                <div className="flex flex-wrap gap-2">
                  {STATUSES.filter((s) => s !== user.account_status).map((s) => (
                    <button
                      key={s}
                      onClick={() => handleStatusChange(s)}
                      className={`px-3 py-1.5 text-xs rounded-lg font-medium border transition-colors ${
                        s === 'ACTIVE'
                          ? 'border-green-200 text-green-700 hover:bg-green-50'
                          : s === 'BANNED'
                          ? 'border-red-200 text-red-700 hover:bg-red-50'
                          : 'border-border text-text-muted hover:bg-surface-muted'
                      }`}
                    >
                      Set {s.replace(/_/g, ' ')}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </aside>
    </div>
  )
}
