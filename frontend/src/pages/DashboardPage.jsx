import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  LogOut, Briefcase, ArrowRight, MailCheck,
  Plus, TrendingUp, FileText, CheckCircle,
  Sparkles, Heart, Cpu, LayoutDashboard, Lock,
  FileSearch, Mail, Send
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { useJobs } from '@/hooks/useJobs'
import { useIntroductions } from '@/hooks/useIntroductions'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import api from '@/lib/api'
import { EmployerCVParser } from '@/pages/employer/EmployerCVParserPage'


// ─── Stat card ────────────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, colour, loading, to, badge }) {
  const content = (
    <div className={`bg-white rounded-xl border border-border p-5 flex items-center gap-4 ${to ? 'hover:border-brand-blue/40 hover:shadow-sm transition-all' : ''}`}>
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${colour}`}>
        <Icon size={18} className="text-white" />
      </div>
      <div>
        {loading ? (
          <div className="h-6 w-10 bg-gray-200 rounded animate-pulse mb-1" />
        ) : (
          <p className="text-2xl font-bold text-text">{value ?? 0}</p>
        )}
        <p className="text-xs text-text-muted flex items-center gap-1.5">
          {label}
          {!loading && badge}
        </p>
      </div>
    </div>
  )
  return to ? <Link to={to}>{content}</Link> : content
}

// ─── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const map = {
    ACTIVE: 'bg-green-100 text-green-700',
    DRAFT: 'bg-amber-100 text-amber-700',
    CLOSED: 'bg-gray-100 text-gray-500',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[status] ?? 'bg-gray-100 text-gray-500'}`}>
      {status}
    </span>
  )
}

// ─── Employer dashboard view ──────────────────────────────────────────────────

function EmployerDashboard({ user }) {
  const [stats, setStats] = useState(null)
  const [statsLoading, setStatsLoading] = useState(true)
  const [profile, setProfile] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')
  const { jobs, loading: jobsLoading } = useJobs({
    endpoint: '/api/v1/jobs/mine',
    params: { limit: 10 }
  })
  const { introductions, loading: introductionsLoading } = useIntroductions()
  const pendingIntroductions = introductions.filter((i) => i.status === 'PENDING').length

  useEffect(() => {
    api.get('/api/v1/employer/stats')
      .then(({ data }) => setStats(data))
      .catch(() => setStats({ total_jobs: 0, active_jobs: 0, draft_jobs: 0, closed_jobs: 0, total_applications: 0 }))
      .finally(() => setStatsLoading(false))

    api.get('/api/v1/employer/profile')
      .then(({ data }) => setProfile(data))
      .catch(() => { })
  }, [])

  const isProfileComplete = user?.is_profile_complete

  const tabs = [
    { id: 'overview', label: 'Console Overview', icon: LayoutDashboard },
    { id: 'talent-pipeline', label: 'Talent Pipeline', icon: Sparkles, badge: 'AI' },
    { id: 'mail-ingestion', label: 'Mail Ingestion', icon: Mail },
    { id: 'saved-candidates', label: 'Saved Candidates', icon: Heart },
    { id: 'ai-recommendations', label: 'AI Recommendations', icon: Cpu, badge: 'AI' },
    { id: 'cv-parser', label: 'CV Parser', icon: FileSearch }
  ]

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text">Welcome Back, {user?.first_name}</h1>
          <p className="text-text-muted text-sm mt-1">
            {profile?.company_name ?? 'Your employer dashboard'}
          </p>
        </div>
        <Link to="/employer/jobs/new">
          <Button className="flex items-center gap-2">
            <Plus size={16} /> Post a Job
          </Button>
        </Link>
      </div>

      {/* Profile incomplete banner */}
      {!isProfileComplete && (
        <div className="rounded-xl border border-brand-amber/30 bg-brand-amber/5 p-4 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-amber-800">Your company profile is incomplete</p>
            <p className="text-xs text-amber-700 mt-0.5">Complete your profile to unlock job posting.</p>
          </div>
          <Link to="/employer/onboarding">
            <Button size="sm" variant="outline" className="border-brand-amber text-brand-amber hover:bg-brand-amber hover:text-white flex-shrink-0">
              Complete profile
            </Button>
          </Link>
        </div>
      )}

      {/* Main Split Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">

        {/* Left column: Navigation tabs list */}
        <nav className="lg:col-span-3 space-y-1.5" aria-label="Dashboard sub-navigation">
          {tabs.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center justify-between px-4 py-3 rounded-lg text-sm font-bold transition-all text-left ${isActive
                    ? 'bg-brand-blue text-white shadow-md'
                    : 'bg-white text-text-muted border border-border hover:bg-surface-muted hover:text-brand-blue'
                  }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon size={18} className={isActive ? 'text-white' : 'text-slate-400'} />
                  <span>{tab.label}</span>
                </div>
                {tab.badge && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-black ${isActive ? 'bg-white/20 text-white' : 'bg-brand-amber/10 text-brand-amber'
                    }`}>
                    {tab.badge}
                  </span>
                )}
              </button>
            )
          })}
        </nav>

        {/* Right column: Tab Content */}
        <div className="lg:col-span-9 space-y-8">
          {activeTab === 'overview' && (
            <>
              {/* Stats */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
                <StatCard icon={Briefcase} label="Total jobs" value={stats?.total_jobs} colour="bg-brand-blue" loading={statsLoading} />
                <StatCard icon={CheckCircle} label="Active" value={stats?.active_jobs} colour="bg-green-500" loading={statsLoading} />
                <StatCard icon={FileText} label="Drafts" value={stats?.draft_jobs} colour="bg-brand-amber" loading={statsLoading} />
                <StatCard icon={TrendingUp} label="Applications" value={stats?.total_applications} colour="bg-purple-500" loading={statsLoading} />
                <StatCard
                  icon={Send}
                  label="Introductions"
                  value={introductions.length}
                  colour="bg-amber-500"
                  loading={introductionsLoading}
                  to="/employer/introductions"
                  badge={pendingIntroductions > 0 && (
                    <span className="px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-semibold">
                      {pendingIntroductions} pending
                    </span>
                  )}
                />
              </div>

              {/* Recent jobs */}
              <div className="bg-white rounded-xl border border-border overflow-hidden">
                <div className="flex items-center justify-between px-5 py-4 border-b border-border">
                  <h2 className="font-semibold text-text text-sm">Recent Jobs</h2>
                  <Link to="/employer/jobs" className="text-brand-blue text-xs font-medium hover:underline">View all</Link>
                </div>

                {jobsLoading && (
                  <div className="p-4 space-y-3">
                    {[1, 2, 3].map(i => (
                      <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
                    ))}
                  </div>
                )}

                {!jobsLoading && jobs.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-12 text-center px-6">
                    <Briefcase size={32} className="text-gray-300 mb-3" />
                    <p className="font-medium text-text text-sm">No jobs posted yet</p>
                    <p className="text-text-muted text-xs mt-1 mb-4">Post your first job to start finding candidates.</p>
                    <Link to="/employer/jobs/new"><Button size="sm">Post a Job</Button></Link>
                  </div>
                )}

                {!jobsLoading && jobs.length > 0 && (
                  <div className="max-h-[280px] overflow-y-auto divide-y divide-border scrollbar-thin scrollbar-thumb-gray-200">
                    <ul>
                      {jobs.map(job => (
                        <li key={job.id} className="flex items-center gap-3 px-5 py-3 border-b border-border last:border-0 hover:bg-surface-muted transition-colors">
                          <div className="flex-1 min-w-0">
                            <Link to={`/jobs/${job.id}`} className="text-sm font-medium text-text hover:text-brand-blue truncate block">{job.title}</Link>
                            <p className="text-xs text-text-muted truncate">{job.location}</p>
                          </div>
                          <StatusBadge status={job.status} />
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Quick actions */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Link to="/employer/jobs/new" className="rounded-xl border border-border bg-white p-5 hover:border-brand-blue/40 hover:shadow-sm transition-all flex items-center gap-4">
                  <div className="w-9 h-9 rounded-lg bg-brand-blue/10 flex items-center justify-center flex-shrink-0">
                    <Plus size={18} className="text-brand-blue" />
                  </div>
                  <div>
                    <p className="font-semibold text-text text-sm">Post a New Job</p>
                    <p className="text-text-muted text-xs mt-0.5">Create a draft and publish when ready</p>
                  </div>
                </Link>
                <Link to="/employer/jobs" className="rounded-xl border border-border bg-white p-5 hover:border-brand-blue/40 hover:shadow-sm transition-all flex items-center gap-4">
                  <div className="w-9 h-9 rounded-lg bg-brand-blue/10 flex items-center justify-center flex-shrink-0">
                    <Briefcase size={18} className="text-brand-blue" />
                  </div>
                  <div>
                    <p className="font-semibold text-text text-sm">Manage Jobs</p>
                    <p className="text-text-muted text-xs mt-0.5">View, edit, publish, or close listings</p>
                  </div>
                </Link>
              </div>
            </>
          )}

          {activeTab === 'talent-pipeline' && (
            <div className="bg-white rounded-xl border border-border p-8 text-center max-w-xl mx-auto space-y-4">
              <div className="w-12 h-12 rounded-full bg-brand-blue/10 text-brand-blue flex items-center justify-center mx-auto">
                <Sparkles size={22} />
              </div>
              <h2 className="text-xl font-bold text-text">Talent Pool</h2>
              <p className="text-text-muted text-sm leading-relaxed">
                Browse your talent pipeline, upload sourced CVs, score candidates against open roles, and promote top matches.
              </p>
              <Link to="/employer/talent-pool">
                <Button className="flex items-center gap-2 mx-auto">
                  Open Talent Pool <ArrowRight size={15} />
                </Button>
              </Link>
            </div>
          )}

          {activeTab === 'mail-ingestion' && (
            <div className="bg-white rounded-xl border border-border p-8 text-center max-w-xl mx-auto space-y-4">
              <div className="w-12 h-12 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto">
                <Mail size={22} />
              </div>
              <h2 className="text-xl font-bold text-text">Mail Ingestion</h2>
              <p className="text-text-muted text-sm leading-relaxed">
                Connect your recruitment mailbox to automatically import and parse CVs.
              </p>
              <Link to="/employer/mail-ingestion">
                <Button className="flex items-center gap-2 mx-auto">
                  Manage Mailboxes <ArrowRight size={15} />
                </Button>
              </Link>
            </div>
          )}

          {activeTab === 'saved-candidates' && (
            <div className="bg-white rounded-xl border border-border p-8 text-center max-w-xl mx-auto space-y-4">
              <div className="w-12 h-12 rounded-full bg-purple-100 text-purple-600 flex items-center justify-center mx-auto shadow border border-purple-200">
                <Heart size={22} />
              </div>
              <h2 className="text-xl font-bold text-text">Saved Candidates</h2>
              <p className="text-text-muted text-sm leading-relaxed">
                Feature coming soon. Bookmark your high-potential hires, build dedicated talent pools, and manage prospective applicant profiles for future roles.
              </p>
              <div className="flex justify-center gap-2 pt-2">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-muted text-text-muted border border-border text-[11px] font-bold">
                  <Lock size={12} /> Upcoming Feature
                </span>
              </div>
            </div>
          )}

          {activeTab === 'ai-recommendations' && (
            <div className="bg-white rounded-xl border border-border p-8 text-center max-w-xl mx-auto space-y-4">
              <div className="w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center mx-auto shadow border border-blue-200">
                <Cpu size={22} />
              </div>
              <h2 className="text-xl font-bold text-text">AI Recommendations</h2>
              <p className="text-text-muted text-sm leading-relaxed">
                Feature coming soon. Smart matching, automated candidate grading, and profile suitability scoring powered by our upcoming recommendation engines.
              </p>
              <div className="flex justify-center gap-2 pt-2">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-muted text-text-muted border border-border text-[11px] font-bold">
                  <Lock size={12} /> Under Development
                </span>
              </div>
            </div>
          )}

          {activeTab === 'cv-parser' && (
            <EmployerCVParser />
          )}

        </div>

      </div>
    </div>
  )
}

// ─── Candidate dashboard view ─────────────────────────────────────────────────

function CandidateDashboard({ user }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Welcome Back, {user?.first_name}</h1>
        <p className="text-text-muted mt-1 text-sm">Find your next opportunity.</p>
      </div>
      <div className="rounded-lg border border-border bg-white p-8 text-center text-text-muted">
        <p className="text-sm">Candidate dashboard coming in Phase 4.</p>
        <Link to="/jobs" className="text-brand-blue text-sm font-medium hover:underline mt-2 inline-block">
          Browse open jobs →
        </Link>
      </div>
    </div>
  )
}

// ─── DashboardPage ────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  // Pending verification — show a minimal notice, not the full dashboard
  if (user?.account_status === 'PENDING_VERIFICATION') {
    return (
      <div className="min-h-screen flex flex-col bg-surface-muted">
        <Navbar />
        <main className="flex-1 pt-16">
          <div className="max-w-2xl mx-auto px-4 py-16">
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 flex items-start gap-4">
              <MailCheck size={22} className="text-amber-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-amber-900 text-sm">Verify your email to continue</p>
                <p className="text-amber-800 text-sm mt-1 leading-relaxed">
                  Check your inbox at <span className="font-medium">{user.email}</span> for the verification link.
                </p>
              </div>
            </div>
          </div>
        </main>
        <Footer />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />
      <main className="flex-1 pt-16">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
          {user?.role === 'EMPLOYER' || user?.role === 'ADMIN'
            ? <EmployerDashboard user={user} />
            : <CandidateDashboard user={user} />
          }
        </div>
      </main>
      <Footer />
    </div>
  )
}
