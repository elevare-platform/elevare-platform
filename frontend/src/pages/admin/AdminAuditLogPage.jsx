import { useEffect, useState, useCallback } from 'react'
import AdminLayout from '@/components/admin/AdminLayout'
import { AdminTable, Th, Td, Pagination } from '@/components/admin/AdminTable'
import { useAdmin } from '@/hooks/useAdmin'

export default function AdminAuditLogPage() {
  const { listAuditLog, loading } = useAdmin()
  const [entries, setEntries] = useState([])
  const [cursor, setCursor] = useState(null)

  const load = useCallback(async (reset = true) => {
    try {
      const params = { limit: 20 }
      if (!reset && cursor) params.cursor = cursor
      const data = await listAuditLog(params)
      setEntries((prev) => reset ? (data.items ?? []) : [...prev, ...(data.items ?? [])])
      setCursor(data.next_cursor ?? null)
    } catch { /* handled */ }
  }, [cursor])

  useEffect(() => { load(true) }, [])

  return (
    <AdminLayout>
      <h1 className="text-2xl font-bold text-text mb-6">Audit Log</h1>

      <AdminTable isEmpty={!loading && entries.length === 0} empty="No audit log entries.">
        <thead>
          <tr>
            <Th>Timestamp</Th>
            <Th>Admin</Th>
            <Th>Action</Th>
            <Th>Target Type</Th>
            <Th>Target ID</Th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id} className="hover:bg-surface-muted/50">
              <Td className="text-xs text-text-muted whitespace-nowrap">
                {new Date(e.created_at).toLocaleString()}
              </Td>
              <Td className="text-sm">
                {e.admin?.first_name} {e.admin?.last_name}
              </Td>
              <Td>
                <span className="font-mono text-xs bg-surface-muted px-2 py-0.5 rounded">
                  {e.action}
                </span>
              </Td>
              <Td className="text-text-muted text-sm">{e.target_type}</Td>
              <Td className="font-mono text-xs text-text-muted truncate max-w-32">
                {e.target_id}
              </Td>
            </tr>
          ))}
        </tbody>
      </AdminTable>

      <Pagination cursor={cursor} onLoadMore={() => load(false)} loading={loading} />
    </AdminLayout>
  )
}
