import { useEffect, useState } from 'react'
import { Users, Briefcase, FileText, Clock, AlertTriangle, UserCheck, RefreshCw } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'
import StatCard from '@/components/admin/StatCard'
import { useAdmin } from '@/hooks/useAdmin'

function AuditFeed({ entries }) {
  if (!entries.length) {
    return <p className="text-text-muted text-sm py-6 text-center">No recent activity.</p>
  }
  return (
    <ul className="divide-y divide-border">
      {entries.map((e) => (
        <li key={e.id} className="py-3 flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-text">
              {e.action.replace(/_/g, ' ')}
            </p>
            <p className="text-xs text-text-muted mt-0.5">
              {e.target_type} · {e.admin?.first_name} {e.admin?.last_name}
            </p>
          </div>
          <time className="text-xs text-text-muted flex-shrink-0">
            {new Date(e.created_at).toLocaleDateString()}
          </time>
        </li>
      ))}
    </ul>
  )
}

export default function AdminDashboardPage() {
  const { getStats, listAuditLog, loading } = useAdmin()
  const [stats, setStats] = useState(null)
  const [recentLog, setRecentLog] = useState([])

  const fetchAll = () => {
    getStats().then(setStats).catch(() => {})
    listAuditLog({ limit: 10 }).then((r) => setRecentLog(r.items ?? [])).catch(() => {})
  }

  useEffect(() => { fetchAll() }, [])

  const u = stats?.users
  const j = stats?.jobs
  const a = stats?.applications

  const cards = [
    { label: 'Total Users', value: u?.total, trend: u?.new_last_30_days, trendLabel: `+${u?.new_last_30_days ?? 0} this month`, icon: Users },
    { label: 'Active Jobs', value: j?.active, trend: j?.new_last_30_days, trendLabel: `+${j?.new_last_30_days ?? 0} this month`, icon: Briefcase },
    { label: 'Total Applications', value: a?.total, trend: a?.new_last_30_days, trendLabel: `+${a?.new_last_30_days ?? 0} this month`, icon: FileText },
    { label: 'New Users (30d)', value: u?.new_last_30_days, icon: UserCheck },
    { label: 'Pending Moderation', value: j?.pending_moderation, icon: AlertTriangle },
    { label: 'Hired This Month', value: a?.hired, icon: Clock },
  ]

  return (
    <AdminLayout>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-text">Dashboard</h1>
        <button
          onClick={fetchAll}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border border-border hover:bg-surface-muted transition-colors disabled:opacity-50"
          aria-label="Refresh stats"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} aria-hidden="true" />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        {cards.map((c) => (
          <StatCard key={c.label} {...c} />
        ))}
      </div>

      <div className="bg-white rounded-xl border border-border p-5">
        <h2 className="text-sm font-semibold text-text mb-4">Recent Activity</h2>
        <AuditFeed entries={recentLog} />
      </div>
    </AdminLayout>
  )
}
