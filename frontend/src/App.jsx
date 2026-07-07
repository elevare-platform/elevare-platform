import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth, getPostAuthRedirect } from '@/context/AuthContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { initAnalytics, trackPageview } from '@/lib/analytics'

// ─── Page-level code splitting ────────────────────────────────────────────────
// Each lazy() call becomes its own JS chunk — only loaded when first visited.

const HomePage = lazy(() => import('@/pages/HomePage'))
const ServicesPage = lazy(() => import('@/pages/ServicesPage'))
const AboutPage = lazy(() => import('@/pages/AboutPage'))
const TalentPipelinePage = lazy(() => import('@/pages/TalentPipelinePage'))
const TrainingPage = lazy(() => import('@/pages/TrainingPage'))
const WorkforceToolsPage = lazy(() => import('@/pages/WorkforceToolsPage'))
const PartnershipPage = lazy(() => import('@/pages/PartnershipPage'))
const HowItWorksPage = lazy(() => import('@/pages/HowItWorksPage'))
const PricingPage = lazy(() => import('@/pages/PricingPage'))
const ContactPage = lazy(() => import('@/pages/ContactPage'))
const PrivacyPage = lazy(() => import('@/pages/PrivacyPage'))
const TermsPage = lazy(() => import('@/pages/TermsPage'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))

const LoginPage = lazy(() => import('@/pages/auth/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/auth/RegisterPage'))
const InviteAcceptPage = lazy(() => import('@/pages/auth/InviteAcceptPage'))
const VerifyEmailPage = lazy(() => import('@/pages/auth/VerifyEmailPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const UnauthorisedPage = lazy(() => import('@/pages/UnauthorisedPage'))

const JobBoardPage = lazy(() => import('@/pages/jobs/JobBoardPage'))
const JobDetailPage = lazy(() => import('@/pages/jobs/JobDetailPage'))

const EmployerJobsPage = lazy(() => import('@/pages/employer/EmployerJobsPage'))
const PostJobPage = lazy(() => import('@/pages/employer/PostJobPage'))
const EditJobPage = lazy(() => import('@/pages/employer/EditJobPage'))
const PublishJobPage = lazy(() => import('@/pages/employer/PublishJobPage'))
const OnboardingPage = lazy(() => import('@/pages/employer/OnboardingPage'))
const ApplicantsPage = lazy(() => import('@/pages/employer/ApplicantsPage'))
const EmployerCVParserPage = lazy(() => import('@/pages/employer/EmployerCVParserPage'))
const TalentPoolPage = lazy(() => import('@/pages/employer/TalentPoolPage'))
const SharedApplicantsPage = lazy(() => import('@/pages/SharedApplicantsPage'))

const AdminInvitePage = lazy(() => import('@/pages/admin/AdminInvitePage'))
const AdminDashboardPage = lazy(() => import('@/pages/admin/AdminDashboardPage'))
const AdminUsersPage = lazy(() => import('@/pages/admin/AdminUsersPage'))
const AdminJobsPage = lazy(() => import('@/pages/admin/AdminJobsPage'))
const AdminApplicationsPage = lazy(() => import('@/pages/admin/AdminApplicationsPage'))
const AdminAuditLogPage = lazy(() => import('@/pages/admin/AdminAuditLogPage'))
const AdminCVParserPage = lazy(() => import('@/pages/admin/AdminCVParserPage'))
const AdminTestimonialsPage = lazy(() => import('@/pages/admin/AdminTestimonialsPage'))
const TestimonialSubmitPage = lazy(() => import('@/pages/TestimonialSubmitPage'))

const CandidateDashboardPage = lazy(() => import('@/pages/candidate/CandidateDashboardPage'))
const CandidateProfilePage = lazy(() => import('@/pages/candidate/CandidateProfilePage'))
const CandidateDocumentsPage = lazy(() => import('@/pages/candidate/CandidateDocumentsPage'))
const MyApplicationsPage = lazy(() => import('@/pages/candidate/MyApplicationsPage'))
const ProfileViewsPage = lazy(() => import('@/pages/candidate/ProfileViewsPage'))

// ─── Shared loading fallback ──────────────────────────────────────────────────

function PageLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-brand-blue border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

// ─── Auth guards ──────────────────────────────────────────────────────────────

function PublicRoute({ children }) {
  const { user, authReady } = useAuth()
  if (!authReady) return <PageLoader />
  return user ? <Navigate to={getPostAuthRedirect(user)} replace /> : children
}

// ─── Routes ───────────────────────────────────────────────────────────────────

function AppRoutes() {
  const location = useLocation()

  useEffect(() => {
    trackPageview(location.pathname + location.search)
  }, [location])

  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/services" element={<ServicesPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/talent-pipeline" element={<TalentPipelinePage />} />
        <Route path="/training" element={<TrainingPage />} />
        <Route path="/workforce-tools" element={<WorkforceToolsPage />} />
        <Route path="/partnership" element={<PartnershipPage />} />
        <Route path="/how-it-works" element={<HowItWorksPage />} />
        <Route path="/pricing" element={<PricingPage />} />
        <Route path="/contact" element={<ContactPage />} />
        <Route path="/testimonials/submit" element={<TestimonialSubmitPage />} />

        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/invite/accept" element={<InviteAcceptPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/unauthorised" element={<UnauthorisedPage />} />

        {/* Public routes — no auth */}
        <Route path="/jobs" element={<JobBoardPage />} />
        <Route path="/jobs/:id" element={<JobDetailPage />} />
        <Route path="/shared/jobs/:token" element={<SharedApplicantsPage />} />

        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<DashboardPage />} />
        </Route>

        {/* Employer-only routes */}
        <Route element={<ProtectedRoute allowedRoles={['EMPLOYER', 'ADMIN']} />}>
          <Route path="/employer/onboarding" element={<OnboardingPage />} />
          <Route path="/employer/jobs" element={<EmployerJobsPage />} />
          <Route path="/employer/jobs/new" element={<PostJobPage />} />
          <Route path="/employer/jobs/:id/edit" element={<EditJobPage />} />
          <Route path="/employer/jobs/:id/publish" element={<PublishJobPage />} />
          <Route path="/employer/jobs/:jobId/applicants" element={<ApplicantsPage />} />
          <Route path="/employer/cv-parser" element={<EmployerCVParserPage />} />
          <Route path="/employer/talent-pool" element={<TalentPoolPage />} />
        </Route>

        {/* Admin-only routes */}
        <Route element={<ProtectedRoute allowedRoles={['ADMIN']} />}>
          <Route path="/admin/invite" element={<AdminInvitePage />} />
          <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
          <Route path="/admin/users" element={<AdminUsersPage />} />
          <Route path="/admin/jobs" element={<AdminJobsPage />} />
          <Route path="/admin/applications" element={<AdminApplicationsPage />} />
          <Route path="/admin/audit-log" element={<AdminAuditLogPage />} />
          <Route path="/admin/cv-parser" element={<AdminCVParserPage />} />
          <Route path="/admin/talent-pool" element={<TalentPoolPage />} />
          <Route path="/admin/testimonials" element={<AdminTestimonialsPage />} />
        </Route>

        {/* Candidate-only routes */}
        <Route element={<ProtectedRoute allowedRoles={['CANDIDATE']} />}>
          <Route path="/candidate/dashboard" element={<CandidateDashboardPage />} />
          <Route path="/candidate/dashboard/documents" element={<CandidateDocumentsPage />} />
          <Route path="/candidate/profile" element={<CandidateProfilePage />} />
          <Route path="/candidate/applications" element={<MyApplicationsPage />} />
          <Route path="/candidate/profile-views" element={<ProfileViewsPage />} />
        </Route>

        {/* Legal */}
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />

        {/* Catch-all — 404 */}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  )
}

export default function App() {
  useEffect(() => {
    initAnalytics()
  }, [])

  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
