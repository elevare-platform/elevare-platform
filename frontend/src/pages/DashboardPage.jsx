import { useNavigate, Link } from 'react-router-dom'
import { LogOut, User, Briefcase, ArrowRight, MailCheck } from 'lucide-react'
import { useAuth, isAccountRestricted } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export default function DashboardPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const restricted = isAccountRestricted(user)

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

      <main className="max-w-4xl mx-auto px-6 py-12 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-text">
            Welcome{restricted ? '' : ' back'}, {user?.first_name}.
          </h1>
          <p className="text-text-muted mt-1">
            Signed in as <span className="font-medium">{user?.email}</span>
            {user?.role && (
              <span className={cn(
                'ml-2 inline-block px-2 py-0.5 rounded-full text-xs font-medium',
                user.role === 'EMPLOYER' ? 'bg-brand-amber/10 text-brand-amber' : 'bg-brand-blue-light text-brand-blue'
              )}>
                {user.role}
              </span>
            )}
          </p>
        </div>

        {/* Pending verification notice — reinforces the banner */}
        {user?.account_status === 'PENDING_VERIFICATION' && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 flex items-start gap-4">
            <MailCheck size={22} className="text-amber-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-amber-900 text-sm">Your email is not verified yet</p>
              <p className="text-amber-800 text-sm mt-1 leading-relaxed">
                You need to verify your email before you can access all platform features.
                Check your inbox at <span className="font-medium">{user.email}</span> for the verification link.
              </p>
              <p className="text-amber-700 text-xs mt-3">
                Can't find it? Check your spam folder, or use the "Resend verification email" link in the banner above.
              </p>
            </div>
          </div>
        )}

        {/* Employer: profile incomplete notice */}
        {user?.role === 'EMPLOYER' && !user?.is_profile_complete && !restricted && (
          <div className="rounded-xl border border-brand-blue/20 bg-brand-blue/5 p-6 flex items-start gap-4">
            <Briefcase size={22} className="text-brand-blue flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-semibold text-brand-blue text-sm">Complete your company profile</p>
              <p className="text-text-muted text-sm mt-1 leading-relaxed">
                Your company profile is incomplete. You need to finish setup before you can post jobs.
              </p>
              <Link to="/employer/onboarding">
                <Button size="sm" className="mt-3 inline-flex items-center gap-1.5">
                  Complete setup <ArrowRight size={14} />
                </Button>
              </Link>
            </div>
          </div>
        )}

        {/* Employer: active with complete profile */}
        {user?.role === 'EMPLOYER' && user?.is_profile_complete && !restricted && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Link
              to="/employer/jobs"
              className="rounded-xl border border-border bg-surface p-6 hover:border-brand-blue/40 hover:shadow-sm transition-all group"
            >
              <Briefcase size={20} className="text-brand-blue mb-3" />
              <p className="font-semibold text-text text-sm">My Jobs</p>
              <p className="text-text-muted text-xs mt-1">Manage your job listings</p>
              <span className="text-brand-blue text-xs font-medium mt-3 inline-flex items-center gap-1 group-hover:gap-2 transition-all">
                View jobs <ArrowRight size={12} />
              </span>
            </Link>
            <Link
              to="/employer/jobs/new"
              className="rounded-xl border border-border bg-surface p-6 hover:border-brand-blue/40 hover:shadow-sm transition-all group"
            >
              <span className="text-2xl mb-3 block">✏️</span>
              <p className="font-semibold text-text text-sm">Post a Job</p>
              <p className="text-text-muted text-xs mt-1">Create a new job listing</p>
              <span className="text-brand-blue text-xs font-medium mt-3 inline-flex items-center gap-1 group-hover:gap-2 transition-all">
                Get started <ArrowRight size={12} />
              </span>
            </Link>
          </div>
        )}

        {/* Candidate dashboard placeholder */}
        {user?.role === 'CANDIDATE' && !restricted && (
          <div className="rounded-lg border border-border bg-surface p-8 text-center text-text-muted">
            <p className="text-sm">Candidate dashboard coming in Phase 4.</p>
            <Link to="/jobs" className="text-brand-blue text-sm font-medium hover:underline mt-2 inline-block">
              Browse open jobs →
            </Link>
          </div>
        )}
      </main>
    </div>
  )
}
