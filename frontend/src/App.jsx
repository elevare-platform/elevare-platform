import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth, getPostAuthRedirect } from '@/context/AuthContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import LoginPage from '@/pages/auth/LoginPage'
import RegisterPage from '@/pages/auth/RegisterPage'
import InviteAcceptPage from '@/pages/auth/InviteAcceptPage'
import DashboardPage from '@/pages/DashboardPage'
import UnauthorisedPage from '@/pages/UnauthorisedPage'
import HomePage from '@/pages/HomePage'
import ServicesPage from '@/pages/ServicesPage'
import AboutPage from '@/pages/AboutPage'
import TalentPipelinePage from '@/pages/TalentPipelinePage'
import TrainingPage from '@/pages/TrainingPage'
import WorkforceToolsPage from '@/pages/WorkforceToolsPage'
import PartnershipPage from '@/pages/PartnershipPage'
import JobBoardPage from '@/pages/jobs/JobBoardPage'
import JobDetailPage from '@/pages/jobs/JobDetailPage'
import EmployerJobsPage from '@/pages/employer/EmployerJobsPage'
import PostJobPage from '@/pages/employer/PostJobPage'
import EditJobPage from '@/pages/employer/EditJobPage'
import OnboardingPage from '@/pages/employer/OnboardingPage'
import AdminInvitePage from '@/pages/admin/AdminInvitePage'
import CandidateDashboardPage from '@/pages/candidate/CandidateDashboardPage'
import CandidateProfilePage from '@/pages/candidate/CandidateProfilePage'
import CandidateDocumentsPage from '@/pages/candidate/CandidateDocumentsPage'
import MyApplicationsPage from '@/pages/candidate/MyApplicationsPage'
import ApplicantsPage from '@/pages/employer/ApplicantsPage'

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

  return user ? <Navigate to={getPostAuthRedirect(user)} replace /> : children
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/services" element={<ServicesPage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/talent-pipeline" element={<TalentPipelinePage />} />
      <Route path="/training" element={<TrainingPage />} />
      <Route path="/workforce-tools" element={<WorkforceToolsPage />} />
      <Route path="/partnership" element={<PartnershipPage />} />

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
        <Route path="/employer/jobs/:id/edit" element={<EditJobPage />} />
        <Route path="/employer/jobs/:jobId/applicants" element={<ApplicantsPage />} />
      </Route>

      {/* Admin-only routes */}
      <Route element={<ProtectedRoute allowedRoles={['ADMIN']} />}>
        <Route path="/admin/invite" element={<AdminInvitePage />} />
      </Route>

      {/* Candidate-only routes */}
      <Route element={<ProtectedRoute allowedRoles={['CANDIDATE']} />}>
        <Route path="/candidate/dashboard" element={<CandidateDashboardPage />} />
        <Route path="/candidate/dashboard/documents" element={<CandidateDocumentsPage />} />
        <Route path="/candidate/profile" element={<CandidateProfilePage />} />
        <Route path="/candidate/applications" element={<MyApplicationsPage />} />
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
