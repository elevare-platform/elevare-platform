import { useCallback, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, CalendarCheck, Send, Upload, User, X } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { Button } from '@/components/ui/button'
import { useInterviewPricing } from '@/hooks/useInterviewPricing'
import { useExampleJobTour } from '@/components/onboarding/useExampleJobTour'
import { interviewPricingNote } from '@/lib/interviewPricing'
import { matchScoreBand } from '@/lib/matchScore'
import { cn } from '@/lib/utils'

// Everything on this page is made up. It never calls the API except for the interview
// price (read only, the same request the real interview list makes), so nothing here can
// be saved, sent or charged. It exists for the guided tour, which ends here.

const JOB_TITLE = 'Sales Manager'

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

const PIPELINE = [
  { id: 'p1', name: 'Segun Adeyemi', note: 'CV uploaded 16 Oct 2026', score: 71 },
  { id: 'p2', name: 'Halima Yusuf', note: 'CV uploaded 16 Oct 2026', score: 46 },
  { id: 'p3', name: 'Ifeanyi Okoro', note: 'CV uploaded just now', score: null },
]

const INTERVIEWS = [
  { id: 'i1', name: 'Amaka Obi', status: 'Not interviewed yet' },
  { id: 'i2', name: 'Segun Adeyemi', status: 'Not interviewed yet' },
  { id: 'i3', name: 'Tunde Bello', status: 'Invite sent' },
]

const STATUS_BADGE = {
  SUBMITTED: 'bg-blue-100 text-blue-700',
  REVIEWING: 'bg-amber-100 text-amber-700',
  SHORTLISTED: 'bg-green-100 text-green-700',
}
const STATUS_LABEL = { SUBMITTED: 'Submitted', REVIEWING: 'Reviewing', SHORTLISTED: 'Shortlisted' }

const TABS = [
  { key: 'applicants', label: 'Applicants' },
  { key: 'pipeline', label: 'Talent Pipeline' },
  { key: 'ai-matches', label: 'AI Talent Matches' },
  { key: 'interviews', label: 'Interview List' },
]

// Shown when this account is not charged for interviews, or the price is not known.
const GENERIC_COST =
  'Each AI interview uses credits, taken when you first send it. You see the cost and your balance here before you send.'

function ScoreBadge({ score, onClick, expanded }) {
  const band = matchScoreBand(score)
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={expanded}
      aria-label={`AI score: ${band.label}`}
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

function ApplicantRow({ applicant, reasoningOpen, onToggleReasoning }) {
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
            <h2 id="example-invite-title" className="text-lg font-bold text-text">Send AI interview invite?</h2>
            <p className="text-sm text-text-muted mt-1">
              {name} will get an email invite to a live AI video interview for this role.
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

/**
 * An example job with made-up applicants. The last stop of the employer's guided tour:
 * applicants and AI scores, uploading CVs to be scored, the interview list, and sending
 * an AI interview with what it costs. Reached from the last dashboard step; closing or
 * finishing the tour returns to the dashboard.
 */
export default function ExampleJobTourPage() {
  const navigate = useNavigate()
  const pricing = useInterviewPricing()
  const realCost = interviewPricingNote(pricing)?.text
  const costText = realCost ?? GENERIC_COST

  const [view, setView] = useState({ tab: 'applicants', reasoning: false, dialog: false })
  const [uploadNote, setUploadNote] = useState(false)
  const [inviteFor, setInviteFor] = useState('Amaka Obi')

  const goToDashboard = useCallback(() => navigate('/dashboard'), [navigate])

  const { start } = useExampleJobTour({
    setView,
    costText: realCost,
    onClosed: goToDashboard,
    autoStart: true,
  })

  const openInvite = (name) => {
    setInviteFor(name)
    setView((v) => ({ ...v, dialog: true }))
  }
  const closeInvite = () => setView((v) => ({ ...v, dialog: false }))
  const showTab = (tab) => setView((v) => ({ ...v, tab, dialog: false }))

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
              <span className="font-semibold">Example job.</span> The candidates and scores are made up.
              Nothing here is real, nothing is sent and no credits are used.
            </p>
            <Button size="sm" variant="outline" onClick={start}>Replay the tour</Button>
          </div>

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
              {APPLICANTS.map((applicant, index) => (
                index === 0 ? (
                  <div key={applicant.id} data-tour="example-score">
                    <ApplicantRow
                      applicant={applicant}
                      reasoningOpen={view.reasoning}
                      onToggleReasoning={() => setView((v) => ({ ...v, reasoning: !v.reasoning }))}
                    />
                  </div>
                ) : (
                  <ApplicantRow key={applicant.id} applicant={applicant} />
                )
              ))}
            </div>
          )}

          {view.tab === 'pipeline' && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-text-muted">External CVs uploaded and scored against this job.</p>
                <button
                  type="button"
                  data-tour="example-upload"
                  onClick={() => setUploadNote(true)}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-white bg-brand-blue px-3 py-1.5 rounded-lg hover:bg-brand-blue-dark transition-colors"
                >
                  <Upload size={12} /> Upload CVs
                </button>
              </div>
              {uploadNote && (
                <p role="status" className="text-xs text-text-muted">
                  In your account this opens the Talent Pool, where you choose the CV files. Nothing is uploaded from this example.
                </p>
              )}
              <div data-tour="example-pipeline-rows" className="space-y-2">
                {PIPELINE.map((profile) => (
                  <div key={profile.id} className="flex items-center gap-4 px-4 py-3 rounded-xl border border-border bg-white">
                    <span className="w-10 h-10 rounded-full border border-border bg-background flex items-center justify-center flex-shrink-0" aria-hidden="true">
                      <User size={16} className="text-text-muted" />
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-text text-sm">{profile.name}</p>
                      <p className="text-xs text-text-muted">{profile.note}</p>
                    </div>
                    <ScoreBadge score={profile.score} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {view.tab === 'ai-matches' && (
            <div className="text-center py-16 rounded-xl border border-dashed border-border bg-white">
              <p className="font-medium text-text text-sm mb-1">AI Talent Matches</p>
              <p className="text-xs text-text-muted">
                In your account, people in your talent pool who fit this job are suggested here. Not part of this example.
              </p>
            </div>
          )}

          {view.tab === 'interviews' && (
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
                {INTERVIEWS.map((item) => (
                  <div key={item.id} className="flex flex-wrap items-center gap-3 px-4 py-3 rounded-xl border border-border bg-white">
                    <CalendarCheck size={16} className="text-brand-blue flex-shrink-0" aria-hidden="true" />
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-text text-sm">{item.name}</p>
                      <p className="text-[11px] text-text-muted">{item.status}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => openInvite(item.name)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-blue text-white hover:bg-brand-blue/90 transition-colors"
                    >
                      <Send size={13} /> Send interview link
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>

      {view.dialog && <SendInviteDialog name={inviteFor} costText={costText} onClose={closeInvite} />}

      <Footer />
    </div>
  )
}
