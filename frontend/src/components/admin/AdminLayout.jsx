import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Users, Briefcase, FileText,
  ScrollText, LogOut, Menu, UserPlus, FileSearch, MessageSquareQuote, Mail,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import ehsLogo from '@/assets/ehs-logo.png'

const NAV = [
  { to: '/admin/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/admin/users', icon: Users, label: 'Users' },
  { to: '/admin/jobs', icon: Briefcase, label: 'Jobs' },
  { to: '/admin/applications', icon: FileText, label: 'Applications' },
  { to: '/admin/cv-parser', icon: FileSearch, label: 'CV Parser' },
  { to: '/admin/testimonials', icon: MessageSquareQuote, label: 'Testimonials' },
  { to: '/admin/audit-log', icon: ScrollText, label: 'Audit Log' },
  { to: '/admin/invite', icon: UserPlus, label: 'Invite' },
  { to: '/employer/mail-ingestion', icon: Mail, label: 'Mail Ingestion' },
]

export default function AdminLayout({ children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const linkClass = ({ isActive }) =>
    `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
      isActive
        ? 'bg-brand-blue text-white'
        : 'text-text-muted hover:bg-surface-muted hover:text-text'
    }`

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      <div className="px-4 py-5 border-b border-border">
        <img src={ehsLogo} alt="Elevare" width={93} height={32} className="h-8 w-auto" />
        <p className="text-xs text-text-muted mt-1">Admin Console</p>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1" aria-label="Admin navigation">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} className={linkClass} onClick={() => setOpen(false)}>
            <Icon size={16} aria-hidden="true" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-border">
        <div className="text-xs text-text-muted px-3 mb-3 truncate">
          {user?.first_name} {user?.last_name}
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-text-muted hover:bg-surface-muted hover:text-text w-full transition-colors"
        >
          <LogOut size={16} aria-hidden="true" />
          <span>Sign out</span>
        </button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen flex bg-surface-muted">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex flex-col w-56 bg-white border-r border-border flex-shrink-0 fixed h-full">
        <SidebarContent />
      </aside>

      {/* Mobile sidebar overlay */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/30" onClick={() => setOpen(false)} />
          <aside className="relative z-50 w-56 bg-white h-full shadow-xl">
            <SidebarContent />
          </aside>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 lg:ml-56 flex flex-col min-h-screen">
        {/* Mobile topbar */}
        <header className="lg:hidden flex items-center justify-between px-4 py-3 bg-white border-b border-border">
          <button
            onClick={() => setOpen(true)}
            className="p-2 rounded-md text-text-muted hover:bg-surface-muted"
            aria-label="Open menu"
          >
            <Menu size={20} />
          </button>
          <img src={ehsLogo} alt="Elevare" width={81} height={28} className="h-7 w-auto" />
          <div className="w-9" />
        </header>

        <main className="flex-1 p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
