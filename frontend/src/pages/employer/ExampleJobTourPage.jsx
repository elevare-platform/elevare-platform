import { useCallback, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Briefcase, CalendarCheck, ChevronDown, Send, TrendingUp, Upload, User, Users, X, Zap,
} from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { Button } from '@/components/ui/button'
import InterviewListButton from '@/components/employer/InterviewListButton'
import { useInterviewPricing } from '@/hooks/useInterviewPricing'
import { useExampleJobTour } from '@/components/onboarding/useExampleJobTour'
import { EXAMPLE_VIEW_DEFAULT } from '@/components/onboarding/tourSteps'
import { interviewPricingNote } from '@/lib/interviewPricing'
import { matchScoreBand } from '@/lib/matchScore'
import { cn } from '@/lib/utils'

// Everything on this page is made up. It never calls the API except for the interview
// price (read only, the same request the real interview list makes), so nothing here can
// be saved, sent or charged. It exists for the guided tour, which ends here. It shows two
// screens, an example job and the Talent Pool, so the tour can walk from one to the other.

const JOB_TITLE = 'Sales Manager'

// What the real pages say, so the example reads the same.
const GENERIC_COST =
  'Each interview uses credits, taken when you first send it. You see the cost and your balance here before you send.'

const APPLICANTS = [
  {
    id: 'a1',
    name: 'Amaka Obi',
    location: 'Lagos',
    years: 6,
    applied: '12 Oct 2026',
    status: 'SHORTLISTED',
    score: 78,
    summary:
      'Six years selling to retailers and distributors, including two years running a regional team. Her results match what this role asks for.',
    strengths: ['Led a team of 8 sales reps', 'Grew a region by 40% in two years'],
    gaps: ['No experience with the products this company sells'],
  },
  { id: 'a2', name: 'Tunde Bello', location: 'Abuja', years: 3, applied: '14 Oct 2026', status: 'REVIEWING', score: 52 },
  { id: 'a3', name: 'Ngozi Eze', location: 'Port Harcourt', years: 1, applied: '15 Oct 2026', status: 'SUBMITTED', score: 31 },
]

// CVs in the talent pool. The scores are against the example job.
const POOL = [
  { id: 'p1', name: 'Segun Adeyemi', source: 'Referral', note: 'Added 16 Oct 2026', score: 71 },
  { id: 'p2', name: 'Halima Yusuf', source: 'Email', note: 'Added 16 Oct 2026', score: 46 },
  { id: 'p3', name: 'Ifeanyi Okoro', source: 'LinkedIn', note: 'Added just now', score: null },
]

const PEOPLE = [...APPLICANTS, ...POOL]

const POOL_JOBS = [
  { value: 'sales', label: JOB_TITLE },
  { value: 'finance', label: 'Finance Officer' },
]

const SOURCES = ['Email', 'Gmail', 'Zoho', 'Referral', 'LinkedIn', 'Other']

const STATUS_BADGE = {
  SUBMITTED: 'bg-blue-100 text-blue-700',
  REVIEWING: 'bg-amber-100 text-amber-700',
  SHORTLISTED: 'bg-green-100 text-green-700',
}
const STATUS_LABEL = { SUBMITTED: 'Submitted', REVIEWING: 'Reviewing', SHORTLISTED: 'Shortlisted' }

const TABS = [
  { key: 'applicants', label: 'Applicants' },
  { key: 'pipeline', label: 'Talent Pipeline' },
  { key: 'ai-matches', label: 'Talent Matches' },
  { key: 'interviews', label: 'Interview List' },
]

function ScoreBadge({ score, onClick, expanded }) {
  const band = matchScoreBand(score)
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={expanded}
      aria-label={`Match score: ${band.label}`}
      className={cn(
        'px-2.5 py-1 rounded-full text-xs font-semibold border whitespace-nowrap',
        onClick ? 'cursor-pointer' : 'cursor-default',
        band.className,
      )}
    >
      {band.label}
    </button>
  )
}

function ApplicantRow({ applicant, reasoningOpen, onToggleReasoning, onList, onToggleList, first }) {
  const interviewButton = <InterviewListButton onList={onList} onToggle={onToggleList} />
  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 p-4">
        <span className="w-10 h-10 rounded-full border border-border bg-background flex items-center justify-center flex-shrink-0" aria-hidden="true">
          <User size={16} className="text-text-muted" />
        </span>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-text text-sm">{applicant.name}</p>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-0.5 text-xs text-text-muted">
            <span>{applicant.location}</span>
            <span>{applicant.years} yr{applicant.years !== 1 ? 's' : ''} exp</span>
            <span>Applied {applicant.applied}</span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 ml-auto">
          {first ? <span data-tour="example-interview-button">{interviewButton}</span> : interviewButton}
          <span className={cn('inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium', STATUS_BADGE[applicant.status])}>
            {STATUS_LABEL[applicant.status]}
          </span>
          <ScoreBadge
            score={applicant.score}
            onClick={applicant.summary ? onToggleReasoning : undefined}
            expanded={applicant.summary ? reasoningOpen : undefined}
          />
          <select
            defaultValue=""
            aria-label="Move application to next status"
            className="rounded-md border border-border bg-background px-3 py-1.5 text-xs text-text"
          >
            <option value="" disabled>Move to...</option>
            <option>Reviewing</option>
            <option>Shortlisted</option>
            <option>Hired</option>
          </select>
        </div>
      </div>

      {applicant.summary && reasoningOpen && (
        <div className="border-t border-border px-4 py-3 bg-background space-y-2">
          <p className="text-[10px] text-text-muted leading-relaxed">
            Reflects how closely this candidate&apos;s experience matches the role, rather than a pass or fail score.
          </p>
          <p className="text-xs text-text leading-relaxed">{applicant.summary}</p>
          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wide text-green-600 mb-1">Strengths</p>
              <ul className="space-y-1">
                {applicant.strengths.map((s) => <li key={s} className="text-xs text-text">✓ {s}</li>)}
              </ul>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wide text-red-500 mb-1">Gaps</p>
              <ul className="space-y-1">
                {applicant.gaps.map((g) => <li key={g} className="text-xs text-text">· {g}</li>)}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function PersonAvatar() {
  return (
    <span className="w-10 h-10 rounded-full border border-border bg-background flex items-center justify-center flex-shrink-0" aria-hidden="true">
      <User size={16} className="text-text-muted" />
    </span>
  )
}

function SendInviteDialog({ name, costText, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="example-invite-title"
        className="w-full max-w-md rounded-xl border border-border bg-white p-6 space-y-4"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="example-invite-title" className="text-lg font-bold text-text">Send interview invite?</h2>
            <p className="text-sm text-text-muted mt-1">
              {name} will get an email invite to a live video interview for this role.
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="text-text-muted hover:text-text flex-shrink-0">
            <X size={18} />
          </button>
        </div>

        <p data-tour="example-cost" className="rounded-lg bg-surface-muted border border-border p-3 text-xs text-text-muted leading-relaxed">
          {costText}
        </p>

        <p className="text-xs text-text-muted">Example only: nothing is sent from here.</p>

        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="px-3 py-1.5 rounded-lg text-xs font-semibold text-text-muted hover:bg-surface-muted transition-colors">
            Skip
          </button>
          <button type="button" onClick={onClose} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-blue text-white hover:bg-brand-blue/90 transition-colors">
            Send interview invite
          </button>
        </div>
      </div>
    </div>
  )
}

// The "Add to Talent Pool" drawer, as on the real Talent Pool page.
function UploadDrawer({ poolJob, onChooseJob, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" aria-hidden="true" />
      <div
        className="relative ml-auto w-full max-w-md bg-white h-full overflow-y-auto shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Add to Talent Pool"
      >
        <div className="flex items-center justify-between px-6 py-5 border-b border-border">
          <div>
            <h2 className="font-semibold text-text text-base">Add to Talent Pool</h2>
            <p className="text-xs text-text-muted mt-0.5">Upload up to 20 CVs (batch processed)</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-surface-muted transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 px-6 py-6 space-y-5">
          <div data-tour="example-pool-drop" className="rounded-xl border-2 border-dashed border-border p-8 text-center">
            <div className="w-12 h-12 rounded-xl bg-brand-blue/10 flex items-center justify-center mx-auto mb-3">
              <Upload size={20} className="text-brand-blue" />
            </div>
            <p className="text-sm font-medium text-text mb-1">Drop PDFs here</p>
            <p className="text-xs text-text-muted">
              or <span className="text-brand-blue font-medium">browse files</span> · up to 20
            </p>
          </div>

          <div>
            <p className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2">Source</p>
            <div className="grid grid-cols-2 gap-2">
              {SOURCES.map((s, i) => (
                <span
                  key={s}
                  className={cn(
                    'px-3 py-2.5 rounded-lg border text-sm font-medium',
                    i === 0 ? 'border-brand-blue bg-brand-blue/5 text-brand-blue' : 'border-border text-text-muted',
                  )}
                >
                  {s}
                </span>
              ))}
            </div>
          </div>

          <div data-tour="example-pool-attach">
            <label htmlFor="example-attach" className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2 block">
              Attach to Job <span className="normal-case font-normal">(optional: enables immediate scoring)</span>
            </label>
            <div className="relative">
              <select
                id="example-attach"
                value={poolJob}
                onChange={(e) => onChooseJob(e.target.value)}
                className="w-full text-sm rounded-lg border border-border px-3 py-2.5 pr-8 appearance-none bg-white"
              >
                <option value="">No job (add to pipeline only)</option>
                {POOL_JOBS.map((job) => <option key={job.value} value={job.value}>{job.label}</option>)}
              </select>
              <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-text-muted" />
            </div>
            {poolJob && (
              <p className="text-xs text-green-600 mt-1.5 flex items-center gap-1">
                <Zap size={11} /> Scoring will run automatically after parsing
              </p>
            )}
          </div>
        </div>

        <div className="px-6 py-5 border-t border-border space-y-2">
          <Button disabled className="w-full" size="lg">Add to Talent Pool</Button>
          <p className="text-xs text-text-muted text-center">Example only: nothing is uploaded from here.</p>
        </div>
      </div>
    </div>
  )
}

function TalentPoolScreen({ view, onChange }) {
  const ranked = view.poolJob !== ''
  const scoreOf = (person) => (view.poolJob === 'sales' ? person.score : null)
  const rows = ranked
    ? [...POOL].sort((a, b) => (scoreOf(b) ?? -1) - (scoreOf(a) ?? -1))
    : POOL
  const jobTitle = POOL_JOBS.find((job) => job.value === view.poolJob)?.label

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-text">Talent Pool</h2>
          <p className="text-sm text-text-muted mt-1">
            {ranked
              ? `Showing candidates ranked against ${jobTitle}`
              : 'Browse your talent pipeline - select a job to see rankings'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {ranked && (
            <Button variant="outline" size="sm" className="flex items-center gap-1.5">
              <Zap size={13} /> Score all
            </Button>
          )}
          <Button size="sm" data-tour="example-pool-add" onClick={() => onChange({ drawer: true })} className="flex items-center gap-1.5">
            <Upload size={13} /> Add CV
          </Button>
        </div>
      </div>

      <div data-tour="example-pool-job" className="rounded-xl border border-border bg-white p-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
          <div className="flex items-center gap-2 flex-shrink-0">
            <Briefcase size={16} className="text-brand-blue" />
            <label htmlFor="example-view-job" className="text-sm font-medium text-text">View against job:</label>
          </div>
          <div className="relative flex-1 max-w-sm w-full">
            <select
              id="example-view-job"
              value={view.poolJob}
              onChange={(e) => onChange({ poolJob: e.target.value })}
              className="w-full text-sm rounded-lg border border-border px-3 py-2 pr-8 appearance-none bg-white"
            >
              <option value="">Pipeline view (no job selected)</option>
              {POOL_JOBS.map((job) => <option key={job.value} value={job.value}>{job.label}</option>)}
            </select>
            <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-text-muted" />
          </div>
          {ranked ? (
            <span className="text-xs text-brand-blue bg-brand-blue/10 px-2.5 py-1 rounded-full font-medium flex items-center gap-1">
              <TrendingUp size={11} /> Ranked by match score
            </span>
          ) : (
            <span className="text-xs text-text-muted bg-surface-muted px-2.5 py-1 rounded-full border border-border">
              Select a job to enable ranking
            </span>
          )}
        </div>
      </div>

      <div className="space-y-3">
        {rows.map((person, index) => (
          <div key={person.id} className="flex items-center gap-4 p-4 rounded-xl border border-border bg-white">
            <span className="w-7 h-7 rounded-full bg-surface-muted text-text-muted text-xs font-bold flex items-center justify-center flex-shrink-0">
              {ranked ? index + 1 : '·'}
            </span>
            <PersonAvatar />
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-text text-sm">{person.name}</p>
              <p className="text-xs text-text-muted mt-0.5">{person.source} · {person.note}</p>
            </div>
            {ranked && <ScoreBadge score={scoreOf(person)} />}
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border bg-blue-100 text-blue-700 border-blue-200">
              New
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * An example job with made-up applicants, and the Talent Pool. The last stop of the
 * employer's guided tour: applicants and AI scores, the interview list button, uploading
 * CVs and choosing the job to score them against, the interview list, and sending an AI
 * interview with what it costs. Reached from the last dashboard step; closing or
 * finishing the tour returns to the dashboard.
 */
export default function ExampleJobTourPage() {
  const navigate = useNavigate()
  const pricing = useInterviewPricing()
  const realCost = interviewPricingNote(pricing)?.text
  const costText = realCost ?? GENERIC_COST

  const [view, setView] = useState(EXAMPLE_VIEW_DEFAULT)
  const [inviteFor, setInviteFor] = useState('Amaka Obi')

  const goToDashboard = useCallback(() => navigate('/dashboard'), [navigate])

  const { start } = useExampleJobTour({
    setView,
    costText: realCost,
    onClosed: goToDashboard,
    autoStart: true,
  })

  const change = (changes) => setView((v) => ({ ...v, ...changes }))
  const showTab = (tab) => change({ tab, dialog: false })
  const toggleListed = (id) => setView((v) => ({
    ...v,
    listed: v.listed.includes(id) ? v.listed.filter((x) => x !== id) : [...v.listed, id],
  }))
  const openInvite = (name) => {
    setInviteFor(name)
    change({ dialog: true })
  }

  const listedPeople = view.listed.map((id) => PEOPLE.find((person) => person.id === id)).filter(Boolean)

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text mb-6 transition-colors"
          >
            <ArrowLeft size={16} />
            Back to dashboard
          </Link>

          <div
            data-tour="example-banner"
            className="mb-6 rounded-xl border border-brand-blue/30 bg-brand-blue/5 p-4 flex flex-wrap items-center justify-between gap-3"
          >
            <p className="text-sm text-text">
              <span className="font-semibold">Example.</span> The candidates and scores are made up.
              Nothing here is real, nothing is sent and no credits are used.
            </p>
            <Button size="sm" variant="outline" onClick={start}>Replay the tour</Button>
          </div>

          {view.page === 'pool' ? (
            <>
              <button
                type="button"
                onClick={() => change({ page: 'job', drawer: false })}
                className="inline-flex items-center gap-1.5 text-sm text-brand-blue hover:underline mb-4"
              >
                <ArrowLeft size={14} /> Back to the example job
              </button>
              <TalentPoolScreen view={view} onChange={change} />
            </>
          ) : (
            <>
              <h1 className="text-2xl font-bold text-text mb-6">Applicants for {JOB_TITLE}</h1>

              <div role="tablist" aria-label="Job sections" className="flex flex-wrap gap-1 p-1 bg-surface-muted rounded-xl border border-border mb-6 w-fit">
                {TABS.map(({ key, label }) => (
                  <button
                    key={key}
                    type="button"
                    role="tab"
                    aria-selected={view.tab === key}
                    onClick={() => showTab(key)}
                    className={cn(
                      'px-4 py-1.5 rounded-lg text-sm font-medium transition-all',
                      view.tab === key
                        ? 'bg-white text-text shadow-sm border border-border'
                        : 'text-text-muted hover:text-text',
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {view.tab === 'applicants' && (
                <div data-tour="example-applicants" className="space-y-3">
                  {APPLICANTS.map((applicant, index) => {
                    const row = (
                      <ApplicantRow
                        applicant={applicant}
                        reasoningOpen={index === 0 ? view.reasoning : false}
                        onToggleReasoning={() => change({ reasoning: !view.reasoning })}
                        onList={view.listed.includes(applicant.id)}
                        onToggleList={() => toggleListed(applicant.id)}
                        first={index === 0}
                      />
                    )
                    return index === 0
                      ? <div key={applicant.id} data-tour="example-score">{row}</div>
                      : <div key={applicant.id}>{row}</div>
                  })}
                </div>
              )}

              {view.tab === 'pipeline' && (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm text-text-muted">External CVs uploaded and scored against this job.</p>
                    <button
                      type="button"
                      data-tour="example-upload"
                      onClick={() => change({ page: 'pool' })}
                      className="inline-flex items-center gap-1.5 text-xs font-semibold text-white bg-brand-blue px-3 py-1.5 rounded-lg hover:bg-brand-blue-dark transition-colors"
                    >
                      <Upload size={12} /> Upload CVs
                    </button>
                  </div>
                  <div data-tour="example-pipeline-rows" className="space-y-2">
                    {POOL.map((profile) => (
                      <div key={profile.id} className="flex flex-wrap items-center gap-4 px-4 py-3 rounded-xl border border-border bg-white">
                        <span className="w-9 h-9 rounded-full bg-brand-blue/10 flex items-center justify-center flex-shrink-0" aria-hidden="true">
                          <Users size={15} className="text-brand-blue" />
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-text">{profile.name}</p>
                          <p className="text-xs text-text-muted">{profile.source} · {profile.note}</p>
                        </div>
                        <ScoreBadge score={profile.score} />
                        <InterviewListButton
                          onList={view.listed.includes(profile.id)}
                          onToggle={() => toggleListed(profile.id)}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {view.tab === 'ai-matches' && (
                <div className="text-center py-16 rounded-xl border border-dashed border-border bg-white">
                  <p className="font-medium text-text text-sm mb-1">Talent Matches</p>
                  <p className="text-xs text-text-muted">
                    In your account, people in your talent pool who fit this job are suggested here. Not part of this example.
                  </p>
                </div>
              )}

              {view.tab === 'interviews' && (listedPeople.length === 0 ? (
                <div className="text-center py-16 rounded-xl border border-dashed border-border bg-white">
                  <CalendarCheck size={28} className="mx-auto text-text-muted mb-3" />
                  <p className="font-medium text-text text-sm mb-1">No one on the interview list yet</p>
                  <p className="text-xs text-text-muted">
                    Add candidates from Applicants, Talent Pipeline, or Talent Matches above.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-xs text-text-muted">{costText}</p>
                  <div className="flex justify-end">
                    <div data-tour="example-send-interviews" className="flex flex-wrap justify-end gap-2">
                      <button type="button" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-border text-text hover:bg-surface-muted transition-colors">
                        Edit interview brief
                      </button>
                      <button
                        type="button"
                        onClick={() => openInvite('everyone on the list')}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-blue text-white hover:bg-brand-blue/90 transition-colors"
                      >
                        <Send size={13} /> Send interview link to all
                      </button>
                    </div>
                  </div>
                  <div data-tour="example-interview-list" className="space-y-3">
                    {listedPeople.map((person) => (
                      <div key={person.id} className="flex flex-wrap items-center gap-3 px-4 py-3 rounded-xl border border-border bg-white">
                        <CalendarCheck size={16} className="text-brand-blue flex-shrink-0" aria-hidden="true" />
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-text text-sm">{person.name}</p>
                          <p className="text-[11px] text-text-muted">Not interviewed yet</p>
                        </div>
                        <InterviewListButton onList onToggle={() => toggleListed(person.id)} />
                        <button
                          type="button"
                          onClick={() => openInvite(person.name)}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-blue text-white hover:bg-brand-blue/90 transition-colors"
                        >
                          <Send size={13} /> Send interview link
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      </main>

      {view.drawer && (
        <UploadDrawer
          poolJob={view.poolJob}
          onChooseJob={(poolJob) => change({ poolJob })}
          onClose={() => change({ drawer: false })}
        />
      )}
      {view.dialog && <SendInviteDialog name={inviteFor} costText={costText} onClose={() => change({ dialog: false })} />}

      <Footer />
    </div>
  )
}
