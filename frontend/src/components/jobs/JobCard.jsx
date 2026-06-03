import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Building2, MapPin, Clock, Bookmark, BookmarkCheck } from 'lucide-react'
import { cn, formatSalary, timeAgo } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { ApplyButton } from '@/components/jobs/ApplyButton'

// ─── Badge colour mapping ─────────────────────────────────────────────────────

const BADGE_CLASSES = {
  DRAFT:         'bg-gray-100 text-gray-500',
  ACTIVE:        'bg-emerald-50 text-emerald-700',
  CLOSED:        'bg-red-50 text-red-600',
  FULL_TIME:     'bg-blue-50 text-blue-700',
  PART_TIME:     'bg-blue-50 text-blue-700',
  CONTRACT:      'bg-purple-50 text-purple-700',
  FREELANCE:     'bg-amber-50 text-amber-700',
  INTERNSHIP:    'bg-teal-50 text-teal-700',
  REMOTE:        'bg-emerald-50 text-emerald-700',
  HYBRID:        'bg-sky-50 text-sky-700',
  ONSITE:        'bg-orange-50 text-orange-700',
  LOCAL:         'bg-slate-100 text-slate-600',
  INTERNATIONAL: 'bg-indigo-50 text-indigo-700',
}

const LABELS = {
  FULL_TIME:     'Full Time',
  PART_TIME:     'Part Time',
  CONTRACT:      'Contract',
  FREELANCE:     'Freelance',
  INTERNSHIP:    'Internship',
  REMOTE:        'Remote',
  HYBRID:        'Hybrid',
  ONSITE:        'Onsite',
  LOCAL:         'Local',
  INTERNATIONAL: 'International',
  DRAFT:         'Draft',
  ACTIVE:        'Active',
  CLOSED:        'Closed',
}

/**
 * Badge — pill with overflow protection and consistent height.
 * max-w ensures long values like "INTERNATIONAL" never break layout.
 */
function Badge({ value, className }) {
  if (!value) return null
  const label = LABELS[value] ?? value
  return (
    <span
      title={label}
      className={cn(
        // Fixed height + padding for consistent sizing across all badges
        'inline-flex items-center h-[22px] px-2.5 rounded-full',
        'text-[11px] font-semibold leading-none whitespace-nowrap',
        // Overflow protection — truncate if somehow too long
        'max-w-[140px] overflow-hidden text-ellipsis',
        BADGE_CLASSES[value] ?? 'bg-gray-100 text-gray-600',
        className
      )}
    >
      {label}
    </span>
  )
}

// ─── Company logo with lazy loading + fallback ────────────────────────────────

function CompanyLogo({ url, name }) {
  const [errored, setErrored] = useState(false)

  const sharedClass = 'w-11 h-11 rounded-xl flex-shrink-0 object-contain'

  if (url && !errored) {
    return (
      <img
        src={url}
        alt={`${name ?? 'Company'} logo`}
        loading="lazy"
        decoding="async"
        onError={() => setErrored(true)}
        className={cn(sharedClass, 'border border-border bg-surface-muted')}
      />
    )
  }

  // Initials-based placeholder — more informative than a generic icon
  const initials = name
    ? name.split(' ').slice(0, 2).map((w) => w[0]).join('').toUpperCase()
    : null

  return (
    <span
      aria-hidden="true"
      className={cn(
        sharedClass,
        'border border-border bg-gradient-to-br from-slate-100 to-slate-200',
        'flex items-center justify-center',
      )}
    >
      {initials ? (
        <span className="text-xs font-bold text-slate-500 leading-none">{initials}</span>
      ) : (
        <Building2 size={18} className="text-slate-400" />
      )}
    </span>
  )
}

// ─── Employer action buttons ──────────────────────────────────────────────────

/**
 * Returns available actions for a given job status.
 * Exported for property testing (Property 9).
 */
export function getJobActions(status) {
  return {
    publish: status === 'DRAFT',
    close:   status === 'ACTIVE',
    edit:    status === 'DRAFT' || status === 'ACTIVE',
    view:    true,
  }
}

function EmployerActions({ job, onPublish, onClose }) {
  const actions = getJobActions(job.status)
  return (
    <div className="flex flex-wrap gap-2 pt-3 border-t border-border" role="group" aria-label="Job actions">
      {actions.publish && (
        <Button
          size="sm"
          onClick={(e) => { e.preventDefault(); onPublish?.(job) }}
          className="bg-emerald-600 hover:bg-emerald-700 text-white border-0 transition-colors"
        >
          Publish
        </Button>
      )}
      {actions.close && (
        <Button
          size="sm"
          variant="destructive"
          onClick={(e) => { e.preventDefault(); onClose?.(job) }}
          className="transition-colors"
        >
          Close
        </Button>
      )}
      {actions.edit && (
        <Link to={`/employer/jobs/${job.id}/edit`}>
          <Button size="sm" variant="outline" className="transition-colors">Edit</Button>
        </Link>
      )}
      {actions.view && (
        <Link to={`/jobs/${job.id}`}>
          <Button size="sm" variant="ghost" className="transition-colors">View</Button>
        </Link>
      )}
      <Link to={`/employer/jobs/${job.id}/applicants`}>
        <Button size="sm" variant="ghost" className="transition-colors">
          View Applicants
          {job.application_count != null && (
            <span className="ml-1.5 inline-flex items-center justify-center w-4 h-4 rounded-full bg-brand-blue text-white text-[10px] font-bold leading-none">
              {job.application_count > 99 ? '99+' : job.application_count}
            </span>
          )}
        </Button>
      </Link>
    </div>
  )
}

// ─── Save / Bookmark button ───────────────────────────────────────────────────

function SaveButton({ saved, onToggle }) {
  return (
    <button
      type="button"
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); onToggle() }}
      aria-label={saved ? 'Remove bookmark' : 'Save job'}
      aria-pressed={saved}
      className={cn(
        'flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg',
        'transition-all duration-150',
        saved
          ? 'text-brand-amber bg-brand-amber/10 hover:bg-brand-amber/20'
          : 'text-slate-400 hover:text-brand-amber hover:bg-brand-amber/10',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-amber focus-visible:ring-offset-1',
      )}
    >
      {saved
        ? <BookmarkCheck size={16} strokeWidth={2} />
        : <Bookmark size={16} strokeWidth={1.75} />}
    </button>
  )
}

// ─── Skill tag ────────────────────────────────────────────────────────────────

function SkillTag({ label }) {
  return (
    <span
      title={label}
      className={cn(
        'inline-flex items-center h-[22px] px-2 rounded-md',
        'bg-slate-50 border border-slate-200',
        'text-[11px] font-medium text-slate-500',
        'whitespace-nowrap max-w-[100px] overflow-hidden text-ellipsis',
      )}
    >
      {label}
    </span>
  )
}

// ─── Skill extraction from description ───────────────────────────────────────

const SKILL_KEYWORDS = [
  'Python', 'JavaScript', 'TypeScript', 'React', 'Vue', 'Angular',
  'Node.js', 'Flutter', 'Dart', 'Swift', 'SwiftUI', 'Kotlin', 'Java',
  'AWS', 'GCP', 'Azure', 'Terraform', 'Kubernetes', 'Docker',
  'PostgreSQL', 'MongoDB', 'Redis', 'SQL', 'MySQL',
  'Figma', 'Sketch', 'Cypress', 'Playwright', 'Selenium',
  'Paystack', 'Flutterwave', 'MLOps', 'Agile', 'Scrum', 'CI/CD',
  'REST', 'GraphQL', 'FastAPI', 'Django', 'Spring',
]

function extractSkills(description = '', max = 4) {
  if (!description) return []
  const lower = description.toLowerCase()
  return SKILL_KEYWORDS
    .filter((kw) => lower.includes(kw.toLowerCase()))
    .slice(0, max)
}

// ─── Card body ────────────────────────────────────────────────────────────────

function CardBody({ job, variant, onPublish, onClose, initialApplied }) {
  const [saved, setSaved] = useState(false)

  const salaryText =
    job.salary_min != null && job.salary_max != null
      ? `${formatSalary(Number(job.salary_min))} – ${formatSalary(Number(job.salary_max))}`
      : null

  const posted = timeAgo(job.created_at)
  const skills = extractSkills(job.description)

  const descPreview = job.description
    ? job.description.length > 110
      ? job.description.slice(0, 110).trimEnd() + '…'
      : job.description
    : null

  return (
    <div className="p-5 flex flex-col gap-3.5 h-full">

      {/* ── Top row: logo + company + save/status ──────────────────────── */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <CompanyLogo url={job.company_logo_url} name={job.company_name} />
          <div className="min-w-0">
            <p className="text-xs font-semibold text-slate-500 truncate leading-tight">
              {job.company_name ?? 'Unknown Company'}
            </p>
            {posted && (
              <p className="flex items-center gap-1 text-[11px] text-slate-400 mt-0.5">
                <Clock size={10} aria-hidden="true" />
                <span>{posted}</span>
              </p>
            )}
          </div>
        </div>

        {variant === 'public' && (
          <SaveButton saved={saved} onToggle={() => setSaved((s) => !s)} />
        )}
        {variant === 'employer' && (
          <Badge value={job.status} />
        )}
      </div>

      {/* ── Title + location ────────────────────────────────────────────── */}
      <div>
        <h3 className="font-bold text-slate-800 text-[15px] leading-snug line-clamp-2 mb-1.5">
          {job.title}
        </h3>
        <p className="flex items-center gap-1.5 text-xs text-slate-500">
          <MapPin size={11} className="flex-shrink-0" aria-hidden="true" />
          <span className="truncate">{job.location}</span>
        </p>
      </div>

      {/* ── Badges ──────────────────────────────────────────────────────── */}
      {/* flex-wrap + min-w-0 on parent prevents overflow */}
      <div className="flex flex-wrap gap-1.5 min-w-0">
        <Badge value={job.contract_type} />
        <Badge value={job.work_model} />
        <Badge value={job.work_location} />
      </div>

      {/* ── Description preview ─────────────────────────────────────────── */}
      {descPreview && (
        <p className="text-xs text-slate-500 leading-relaxed line-clamp-2 flex-shrink-0">
          {descPreview}
        </p>
      )}

      {/* ── Skills ──────────────────────────────────────────────────────── */}
      {skills.length > 0 && (
        <div className="flex flex-wrap gap-1.5 min-w-0">
          {skills.map((s) => <SkillTag key={s} label={s} />)}
        </div>
      )}

      {/* ── Spacer pushes footer to bottom ──────────────────────────────── */}
      <div className="flex-1" />

      {/* ── Footer: salary + apply ──────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-3 pt-3 border-t border-slate-100">
        <div className="min-w-0">
          {salaryText ? (
            <p className="text-sm font-bold text-slate-800 truncate">{salaryText}</p>
          ) : (
            <p className="text-xs text-slate-400 italic">Salary not disclosed</p>
          )}
        </div>

        {variant === 'public' && (
          <div className="flex items-center gap-2 flex-shrink-0">
            <Link
              to={`/jobs/${job.id}`}
              onClick={(e) => e.stopPropagation()}
              className="text-xs font-medium text-text-muted hover:text-brand-blue transition-colors focus-visible:outline-none"
            >
              View details
            </Link>
            <ApplyButton jobId={job.id} jobStatus={job.status} size="sm" initialApplied={initialApplied} />
          </div>
        )}
      </div>

      {/* ── Employer actions ────────────────────────────────────────────── */}
      {variant === 'employer' && (
        <EmployerActions job={job} onPublish={onPublish} onClose={onClose} />
      )}
    </div>
  )
}

// ─── JobCard ──────────────────────────────────────────────────────────────────

/**
 * JobCard — premium job listing card.
 *
 * @param {Object}   props
 * @param {Object}   props.job
 * @param {'public'|'employer'} [props.variant='public']
 * @param {Function} [props.onPublish]
 * @param {Function} [props.onClose]
 */
export function JobCard({ job, variant = 'public', onPublish, onClose, initialApplied = null }) {
  const base = cn(
    'group rounded-2xl border border-slate-200 bg-white',
    // Subtle shadow that lifts on hover — no oversized shadows
    'shadow-[0_1px_3px_rgba(0,0,0,0.06),0_1px_2px_rgba(0,0,0,0.04)]',
    'hover:shadow-[0_8px_24px_rgba(0,0,0,0.10),0_2px_6px_rgba(0,0,0,0.06)]',
    'hover:-translate-y-1',
    'transition-all duration-200 ease-out',
    // Ensure cards in a grid row share the same height
    'flex flex-col',
  )

  if (variant === 'public') {
    return (
      <div className={cn(base, 'focus-visible:outline-none')} role="article">
        <CardBody job={job} variant="public" initialApplied={initialApplied} />
      </div>
    )
  }

  return (
    <div className={base} role="article">
      <CardBody job={job} variant="employer" onPublish={onPublish} onClose={onClose} />
    </div>
  )
}
