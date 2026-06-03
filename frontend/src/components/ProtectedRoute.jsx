import { Navigate, Outlet } from 'react-router-dom'
import { useAuth, isAccountRestricted } from '@/context/AuthContext'
import { AccountStatusBanner } from '@/components/AccountStatusBanner'

export function ProtectedRoute({ allowedRoles }) {
  const { user, authReady } = useAuth()

  if (!authReady) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-brand-blue border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  // Truly unauthenticated — no session at all
  if (!user) return <Navigate to="/login" replace />

  // Authenticated but restricted (pending verification, suspended, etc.)
  // Show the banner above the page rather than redirecting to login.
  // The page itself is responsible for gracefully disabling restricted actions.
  if (isAccountRestricted(user)) {
    return (
      <>
        <div className="pt-16">
          <AccountStatusBanner />
        </div>
        <RestrictedPage user={user} allowedRoles={allowedRoles} />
      </>
    )
  }

  // Role check — active user but wrong role
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/unauthorised" replace />
  }

  return <Outlet />
}

// ─── RestrictedPage ───────────────────────────────────────────────────────────
// Shown when a user is authenticated but their account status blocks access.
// Renders a clear explanation instead of a blank screen or login redirect.

function RestrictedPage({ user, allowedRoles }) {
  const status = user.account_status

  // PENDING_VERIFICATION: let them see the dashboard shell with the banner.
  // They can still browse public pages; the banner handles the CTA.
  if (status === 'PENDING_VERIFICATION') {
    // If they're trying to access a role-gated route they don't have, still block that
    if (allowedRoles && !allowedRoles.includes(user.role)) {
      return <Navigate to="/unauthorised" replace />
    }
    return <Outlet />
  }

  // SUSPENDED / BANNED / DEACTIVATED: show a dedicated blocked screen
  return (
    <div className="min-h-screen bg-surface-muted flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center space-y-4">
        <div className="w-14 h-14 rounded-full bg-red-100 flex items-center justify-center mx-auto">
          <span className="text-2xl">🚫</span>
        </div>
        <h1 className="text-xl font-bold text-text">Access restricted</h1>
        <p className="text-text-muted text-sm leading-relaxed">
          {status === 'SUSPENDED' && 'Your account has been temporarily suspended. Please contact support for assistance.'}
          {status === 'BANNED' && 'Your account has been permanently banned due to a violation of our terms of service.'}
          {status === 'DEACTIVATED' && 'Your account has been deactivated. Contact support if you believe this is a mistake.'}
        </p>
        <a
          href="mailto:support@elevarehuman.com"
          className="inline-block text-sm text-brand-blue hover:underline"
        >
          Contact support
        </a>
      </div>
    </div>
  )
}
