import { useNavigate } from 'react-router-dom'
import { LogOut, User } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'

export default function DashboardPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-surface-muted">
      {/* Top nav */}
      <header className="bg-surface border-b border-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded bg-brand-blue flex items-center justify-center">
            <span className="text-white font-bold text-xs">E</span>
          </div>
          <span className="font-semibold text-text">Elevare</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-text-muted">
            <User size={16} />
            <span>{user?.first_name} {user?.last_name}</span>
          </div>
          <Button variant="outline" size="sm" onClick={handleLogout}>
            <LogOut size={14} className="mr-2" />
            Sign out
          </Button>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-6 py-12 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-text">
            Welcome back, {user?.first_name}.
          </h1>
          <p className="text-text-muted mt-1">
            You're signed in as <span className="font-medium">{user?.email}</span>
            {user?.role && (
              <span className="ml-2 inline-block px-2 py-0.5 rounded-full bg-brand-blue-light text-brand-blue text-xs font-medium">
                {user.role}
              </span>
            )}
          </p>
        </div>

        <div className="rounded-lg border border-border bg-surface p-8 text-center text-text-muted">
          Dashboard content coming soon.
        </div>
      </main>
    </div>
  )
}
