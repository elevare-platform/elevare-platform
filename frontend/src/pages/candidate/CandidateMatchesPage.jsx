import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  BrainCircuit, Building2, MapPin, Briefcase, ChevronRight,
  Sparkles, AlertCircle,
} from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

// ─── Score badge ──────────────────────────────────────────────────────────────

function ScoreBadge({ score }) {
  const colour =
    score >= 75 ? 'bg-emerald-100 text-emerald-700' :
    score >= 50 ? 'bg-amber-100 text-amber-700' :
    'bg-gray-100 text-gray-500'
  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold', colour)}>
      <Sparkles size={10} /> {score}% match
    </span>
  )
}

// ─── Job match card ───────────────────────────────────────────────────────────

function MatchCard({ match }) {
  const { job, similarity_score } = match

  return (
    <div className="bg-white rounded-xl border border-border p-5 hover:border-brand-blue/40 hover:shadow-md transition-all">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-3 min-w-0">
          {job.company_logo_url ? (
            <img src={job.company_logo_url} alt="" className="w-10 h-10 rounded-lg object-contain border border-border flex-shrink-0" />
          ) : (
            <span className="w-10 h-10 rounded-lg border border-border bg-surface-muted flex items-center justify-center flex-shrink-0">
              <Building2 size={16} className="text-text-muted" />
            </span>
          )}
          <div className="min-w-0">
            <p className="font-semibold text-text text-sm truncate">{job.title}</p>
            <p className="text-xs text-text-muted truncate">{job.company_name ?? 'Company'}</p>
          </div>
        </div>
        <ScoreBadge score={similarity_score} />
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 mb-4">
        {job.location && (
          <span className="flex items-center gap-1 text-xs text-text-muted">
            <MapPin size={11} /> {job.location}
          </span>
        )}
        {job.contract_type && (
          <span className="flex items-center gap-1 text-xs text-text-muted">
            <Briefcase size={11} /> {job.contract_type}
          </span>
        )}
        {job.seniority_level && (
          <span className="text-xs text-text-muted">{job.seniority_level}</span>
        )}
      </div>

      {job.required_skills?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          {job.required_skills.slice(0, 6).map((s) => {
            const isMatched = match.matched_skills?.some(
              (ms) => ms.toLowerCase() === s.toLowerCase()
            )
            return (
              <span
                key={s}
                className={cn(
                  'text-[11px] px-2 py-0.5 rounded-full border',
                  isMatched
                    ? 'bg-green-50 text-green-700 border-green-200 font-semibold'
                    : 'bg-surface-muted text-text-muted border-border'
                )}
              >
                {s}
              </span>
            )
          })}
          {job.required_skills.length > 6 && (
            <span className="text-[11px] text-text-muted px-1">+{job.required_skills.length - 6}</span>
          )}
        </div>
      )}

      <div className="flex items-center justify-between">
        <span className="text-[11px] text-text-muted">
          {job.work_model ? `${job.work_model} · ` : ''}{job.work_location}
        </span>
        <Link to={`/jobs/${job.id}`}>
          <Button size="sm" className="text-xs h-7 px-3">
            View Job <ChevronRight size={12} className="ml-1" />
          </Button>
        </Link>
      </div>
    </div>
  )
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function Skeleton({ className }) {
  return <div className={cn('animate-pulse bg-gray-200 rounded', className)} />
}

function MatchCardSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-border p-5 space-y-3">
      <div className="flex items-center gap-3">
        <Skeleton className="w-10 h-10 rounded-lg flex-shrink-0" />
        <div className="flex-1 space-y-1.5">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-3 w-1/3" />
        </div>
        <Skeleton className="h-5 w-20 rounded-full" />
      </div>
      <div className="flex gap-3">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-3 w-16" />
      </div>
      <div className="flex gap-1.5">
        {[1,2,3].map(i => <Skeleton key={i} className="h-5 w-16 rounded-full" />)}
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CandidateMatchesPage() {
  const [matches, setMatches] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.get('/api/v1/candidates/me/matches', { params: { limit: 20 } })
      .then(({ data }) => setMatches(data ?? []))
      .catch(() => setError('Could not load matches right now.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-10 space-y-6">

          {/* Header */}
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-brand-blue/10 flex items-center justify-center">
                <BrainCircuit size={20} className="text-brand-blue" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-text">Jobs Matched to You</h1>
                <p className="text-sm text-text-muted">Ranked by how well your profile fits each role</p>
              </div>
            </div>
            <Link to="/jobs">
              <Button variant="outline" size="sm" className="text-xs">Browse all jobs</Button>
            </Link>
          </div>

          {/* States */}
          {loading && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[1,2,3,4].map(i => <MatchCardSkeleton key={i} />)}
            </div>
          )}

          {!loading && error && (
            <div className="flex items-center gap-3 bg-red-50 border border-red-200 rounded-xl px-5 py-4 text-sm text-red-600">
              <AlertCircle size={16} className="flex-shrink-0" /> {error}
            </div>
          )}

          {!loading && !error && matches.length === 0 && (
            <div className="bg-white rounded-xl border border-border p-10 text-center space-y-3">
              <BrainCircuit size={32} className="text-gray-300 mx-auto" />
              <p className="font-medium text-text">No matches yet</p>
              <p className="text-sm text-text-muted max-w-xs mx-auto">
                Upload a CV and complete your profile so our AI can find the best-fit roles for you.
              </p>
              <Link to="/candidate/profile">
                <Button size="sm" className="mt-2">Complete Profile</Button>
              </Link>
            </div>
          )}

          {!loading && !error && matches.length > 0 && (
            <>
              <p className="text-sm text-text-muted">{matches.length} role{matches.length !== 1 ? 's' : ''} found</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {matches.map((m, i) => <MatchCard key={m.job.id ?? i} match={m} />)}
              </div>
            </>
          )}

        </div>
      </main>

      <Footer />
    </div>
  )
}
