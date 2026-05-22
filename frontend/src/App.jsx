import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/context/AuthContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import LoginPage from '@/pages/auth/LoginPage'
import RegisterPage from '@/pages/auth/RegisterPage'
import InviteAcceptPage from '@/pages/auth/InviteAcceptPage'
import DashboardPage from '@/pages/DashboardPage'
import UnauthorisedPage from '@/pages/UnauthorisedPage'
import HomePage from '@/pages/HomePage'
import JobBoardPage from '@/pages/jobs/JobBoardPage'
import JobDetailPage from '@/pages/jobs/JobDetailPage'
import EmployerJobsPage from '@/pages/employer/EmployerJobsPage'
import PostJobPage from '@/pages/employer/PostJobPage'
import OnboardingPage from '@/pages/employer/OnboardingPage'
import AdminInvitePage from '@/pages/admin/AdminInvitePage'

// Redirects authenticated users away from login/register
function PublicRoute({ children }) {
  const { user, authReady } = useAuth()

  if (!authReady) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-brand-blue border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return user ? <Navigate to="/dashboard" replace /> : children
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />

      <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
      <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />
      <Route path="/invite/accept" element={<PublicRoute><InviteAcceptPage /></PublicRoute>} />
      <Route path="/unauthorised" element={<UnauthorisedPage />} />

      {/* Public job routes */}
      <Route path="/jobs" element={<JobBoardPage />} />
      <Route path="/jobs/:id" element={<JobDetailPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<DashboardPage />} />
      </Route>

      {/* Employer-only routes */}
      <Route element={<ProtectedRoute allowedRoles={['EMPLOYER', 'ADMIN']} />}>
        <Route path="/employer/onboarding" element={<OnboardingPage />} />
        <Route path="/employer/jobs" element={<EmployerJobsPage />} />
        <Route path="/employer/jobs/new" element={<PostJobPage />} />
      </Route>

      {/* Admin-only routes */}
      <Route element={<ProtectedRoute allowedRoles={['ADMIN']} />}>
        <Route path="/admin/invite" element={<AdminInvitePage />} />
      </Route>

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes>
        </AppRoutes>
      </AuthProvider>
    </BrowserRouter>
  )
}
