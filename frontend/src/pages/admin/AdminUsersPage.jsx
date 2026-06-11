import { useEffect, useState, useCallback } from 'react'
import { Search } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'
import { AdminTable, Th, Td, Pagination } from '@/components/admin/AdminTable'
import StatusBadge from '@/components/admin/StatusBadge'
import UserDetailDrawer from '@/components/admin/UserDetailDrawer'
import ConfirmModal from '@/components/admin/ConfirmModal'
import { useToast } from '@/components/admin/Toast'
import { useAdmin } from '@/hooks/useAdmin'

const ROLES = ['', 'CANDIDATE', 'EMPLOYER', 'ADMIN']
const STATUSES = ['', 'ACTIVE', 'PENDING_VERIFICATION', 'SUSPENDED', 'DEACTIVATED', 'BANNED']

export default function AdminUsersPage() {
  const { listUsers, updateUserStatus, bulkUpdateUsers, loading } = useAdmin()
  const { show, ToastContainer } = useToast()
  const [users, setUsers] = useState([])
  const [cursor, setCursor] = useState(null)
  const [search, setSearch] = useState('')
  const [role, setRole] = useState('')
  const [status, setStatus] = useState('')
  const [selected, setSelected] = useState([])
  const [drawerUserId, setDrawerUserId] = useState(null)
  const [confirm, setConfirm] = useState(null) // { userId, action } or { bulk: true, action }

  const load = useCallback(async (reset = true, overrideCursor) => {
    try {
      const params = { limit: 20 }
      if (search) params.search = search
      if (role) params.role = role
      if (status) params.status = status
      if (!reset) params.cursor = overrideCursor ?? cursor
      const data = await listUsers(params)
      setUsers((prev) => reset ? (data.items ?? []) : [...prev, ...(data.items ?? [])])
      setCursor(data.next_cursor ?? null)
      if (reset) setSelected([])
    } catch { /* handled in hook */ }
  }, [search, role, status, cursor])

  useEffect(() => { load(true) }, [search, role, status])

  const handleStatusChange = async (userId, newStatus) => {
    try {
      await updateUserStatus(userId, newStatus)
      setUsers((prev) => prev.map((u) => u.id === userId ? { ...u, account_status: newStatus } : u))
      show(`Status updated to ${newStatus.replace(/_/g, ' ')}`)
    } catch {
      show('Failed to update status', 'error')
    }
  }

  const handleBulk = async (action) => {
    if (!selected.length) return
    try {
      await bulkUpdateUsers(selected, action)
      setUsers((prev) =>
        prev.map((u) => selected.includes(u.id) ? { ...u, account_status: action } : u)
      )
      show(`${selected.length} users updated`)
      setSelected([])
    } catch {
      show('Bulk update failed', 'error')
    }
    setConfirm(null)
  }

  const toggleSelect = (id) =>
    setSelected((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])

  const toggleAll = () =>
    setSelected(selected.length === users.length ? [] : users.map((u) => u.id))

  return (
    <AdminLayout>
      <ToastContainer />

      {drawerUserId && (
        <UserDetailDrawer
          userId={drawerUserId}
          onClose={() => setDrawerUserId(null)}
          onStatusChange={(id, s) => {
            setUsers((prev) => prev.map((u) => u.id === id ? { ...u, account_status: s } : u))
            show(`Status updated to ${s.replace(/_/g, ' ')}`)
          }}
        />
      )}

      {confirm && (
        <ConfirmModal
          title={confirm.bulk ? `${confirm.action} ${selected.length} users?` : `${confirm.action} this user?`}
          description="This action will be recorded in the audit log."
          confirmLabel={confirm.action}
          danger={['DEACTIVATED', 'SUSPENDED', 'BANNED'].includes(confirm.action)}
          requireReason
          onConfirm={() => confirm.bulk ? handleBulk(confirm.action) : handleStatusChange(confirm.userId, confirm.action)}
          onCancel={() => setConfirm(null)}
        />
      )}

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-text">Users</h1>
        {selected.length > 0 && (
          <div className="flex gap-2">
            <button
              onClick={() => setConfirm({ bulk: true, action: 'ACTIVE' })}
              className="px-3 py-1.5 text-sm rounded-lg bg-green-100 text-green-700 hover:bg-green-200 transition-colors"
            >
              Activate ({selected.length})
            </button>
            <button
              onClick={() => setConfirm({ bulk: true, action: 'DEACTIVATED' })}
              className="px-3 py-1.5 text-sm rounded-lg bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
            >
              Deactivate ({selected.length})
            </button>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" aria-hidden="true" />
          <input
            type="search"
            placeholder="Search name or email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-2 text-sm rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-brand-blue"
            aria-label="Search users"
          />
        </div>
        <select value={role} onChange={(e) => setRole(e.target.value)}
          className="text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue"
          aria-label="Filter by role">
          {ROLES.map((r) => <option key={r} value={r}>{r || 'All roles'}</option>)}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}
          className="text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue"
          aria-label="Filter by status">
          {STATUSES.map((s) => <option key={s} value={s}>{s || 'All statuses'}</option>)}
        </select>
      </div>

      <AdminTable isEmpty={!loading && users.length === 0} empty="No users found.">
        <thead>
          <tr>
            <Th>
              <input type="checkbox"
                checked={selected.length === users.length && users.length > 0}
                onChange={toggleAll} aria-label="Select all users" />
            </Th>
            <Th>Name</Th>
            <Th>Email</Th>
            <Th>Role</Th>
            <Th>Status</Th>
            <Th>Joined</Th>
            <Th>Actions</Th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className="hover:bg-surface-muted/50">
              <Td>
                <input type="checkbox" checked={selected.includes(u.id)}
                  onChange={() => toggleSelect(u.id)} aria-label={`Select ${u.first_name}`} />
              </Td>
              <Td>
                <button
                  onClick={() => setDrawerUserId(u.id)}
                  className="font-medium text-brand-blue hover:underline text-left"
                >
                  {u.first_name} {u.last_name}
                </button>
              </Td>
              <Td className="text-text-muted">{u.email}</Td>
              <Td><StatusBadge value={u.role} /></Td>
              <Td><StatusBadge value={u.account_status} /></Td>
              <Td className="text-text-muted text-xs">{new Date(u.created_at).toLocaleDateString()}</Td>
              <Td>
                <div className="flex gap-2">
                  <button onClick={() => setDrawerUserId(u.id)}
                    className="text-xs text-text-muted hover:text-brand-blue hover:underline">
                    View
                  </button>
                  {u.role !== 'ADMIN' && u.account_status !== 'ACTIVE' && (
                    <button
                      onClick={() => setConfirm({ userId: u.id, action: 'ACTIVE' })}
                      className="text-xs text-green-700 hover:underline">
                      Activate
                    </button>
                  )}
                  {u.role !== 'ADMIN' && u.account_status === 'ACTIVE' && (
                    <button
                      onClick={() => setConfirm({ userId: u.id, action: 'DEACTIVATED' })}
                      className="text-xs text-red-600 hover:underline">
                      Deactivate
                    </button>
                  )}
                  {u.role !== 'ADMIN' && !['BANNED', 'SUSPENDED'].includes(u.account_status) && (
                    <button
                      onClick={() => setConfirm({ userId: u.id, action: 'BANNED' })}
                      className="text-xs text-red-800 hover:underline">
                      Ban
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
