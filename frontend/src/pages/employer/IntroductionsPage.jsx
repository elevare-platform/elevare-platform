import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Send, Clock, CheckCircle2, XCircle, User, Briefcase } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { cn } from '@/lib/utils'
import { useIntroductions } from '@/hooks/useIntroductions'

const STATUS_STYLES = {
  PENDING: { icon: Clock, label: 'Pending', className: 'bg-amber-50 text-amber-700 border-amber-200' },
  ACCEPTED: { icon: CheckCircle2, label: 'Accepted', className: 'bg-green-50 text-green-700 border-green-200' },
  DECLINED: { icon: XCircle, label: 'Declined', className: 'bg-gray-100 text-gray-500 border-gray-200' },
  EXPIRED: { icon: Clock, label: 'Expired', className: 'bg-gray-100 text-gray-500 border-gray-200' },
}

const FILTER_TABS = ['all', 'PENDING', 'ACCEPTED', 'DECLINED', 'EXPIRED']

function formatDate(isoString) {
  if (!isoString) return null
  return new Date(isoString).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

function StatusBadge({ status }) {
  const config = STATUS_STYLES[status] ?? STATUS_STYLES.PENDING
  const Icon = config.icon
  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border flex-shrink-0',
      config.className
    )}>
      <Icon size={12} />
      {config.label}
    </span>
  )
}

function IntroductionRow({ intro }) {
  const displayName = intro.candidate_name ?? 'Private profile'

  return (
    <div className="rounded-xl border border-border bg-white p-4 flex flex-wrap items-center gap-4">
      <span className="w-10 h-10 rounded-full bg-brand-blue/10 flex items-center justify-center flex-shrink-0">
        <User size={16} className="text-brand-blue" />
      </span>

      <div className="flex-1 min-w-0">
        <p className="font-semibold text-text text-sm truncate">{displayName}</p>
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-0.5 text-xs text-text-muted">
          {intro.candidate_current_title && <span>{intro.candidate_current_title}</span>}
          <Link
            to={`/employer/jobs/${intro.job_id}/applicants`}
            className="flex items-center gap-1 text-brand-blue hover:underline"
          >
            <Briefcase size={11} />
            {intro.job_title}
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-xs text-text-muted">
        <span>Requested {formatDate(intro.created_at)}</span>
        {intro.responded_at && <span>· Responded {formatDate(intro.responded_at)}</span>}
        {intro.status === 'PENDING' && <span>· Expires {formatDate(intro.expires_at)}</span>}
      </div>

      <StatusBadge status={intro.status} />
    </div>
  )
}

function SkeletonRow() {
  return (
    <div className="rounded-xl border border-border bg-white p-4 flex items-center gap-4 animate-pulse">
      <div className="w-10 h-10 rounded-full bg-gray-200 flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="h-4 bg-gray-200 rounded w-1/3" />
        <div className="h-3 bg-gray-200 rounded w-1/2" />
      </div>
      <div className="h-6 bg-gray-200 rounded-full w-20" />
    </div>
  )
}

export default function IntroductionsPage() {
  const { introductions, loading, error, refetch } = useIntroductions()
  const [activeTab, setActiveTab] = useState('all')

  const filtered = activeTab === 'all'
    ? introductions
    : introductions.filter((i) => i.status === activeTab)

  const countFor = (tab) =>
    tab === 'all' ? introductions.length : introductions.filter((i) => i.status === tab).length

  return (
    <>
      <Navbar />

      <main className="min-h-screen bg-background pt-16">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-2xl font-bold text-text flex items-center gap-2">
              <Send size={22} className="text-brand-blue" />
              My Introductions
            </h1>
            <button type="button" onClick={refetch} className="text-xs text-brand-blue hover:underline">
              Refresh
            </button>
          </div>
          <p className="text-sm text-text-muted mb-6">
            Every introduction request you've made across all your job postings.
          </p>

          <div className="flex flex-wrap gap-1.5 mb-6" role="tablist" aria-label="Filter by status">
            {FILTER_TABS.map((tab) => (
              <button
                key={tab}
                role="tab"
                aria-selected={activeTab === tab}
                onClick={() => setActiveTab(tab)}
                className={cn(
                  'px-3 py-1.5 rounded-full text-xs font-medium capitalize transition-colors',
                  activeTab === tab
                    ? 'bg-brand-blue text-white'
                    : 'bg-surface border border-border text-text-muted hover:text-text'
                )}
              >
                {tab === 'all' ? 'All' : STATUS_STYLES[tab].label} ({countFor(tab)})
              </button>
            ))}
          </div>

          {error && <p className="text-sm text-red-600 mb-4" role="alert">{error}</p>}

          {loading && (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => <SkeletonRow key={i} />)}
            </div>
          )}

          {!loading && !error && filtered.length === 0 && (
            <div className="text-center py-20">
              <Send size={28} className="mx-auto text-text-muted mb-3" />
              <p className="text-lg font-semibold text-text mb-1">
                {activeTab === 'all' ? 'No introductions yet' : `No ${STATUS_STYLES[activeTab]?.label.toLowerCase()} introductions`}
              </p>
              <p className="text-sm text-text-muted">
                Request introductions to matched candidates from a job's AI Talent Matches tab.
              </p>
            </div>
          )}

          {!loading && filtered.length > 0 && (
            <div className="space-y-3">
              {filtered.map((intro) => <IntroductionRow key={intro.id} intro={intro} />)}
            </div>
          )}
        </div>
      </main>

      <Footer />
    </>
  )
}
