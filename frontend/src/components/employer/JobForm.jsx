import React from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FormField, FormMessage } from '@/components/ui/form'
import { WorkLocationToggle } from '@/components/jobs/WorkLocationToggle'
import { cn } from '@/lib/utils'

const jobSchema = z
  .object({
    title: z.string().min(3, 'Title must be at least 3 characters').max(150),
    // Structured description fields
    about_the_role: z.string().min(10, 'About the Role must be at least 10 characters'),
    key_responsibilities: z.string().min(10, 'Key Responsibilities must be at least 10 characters'),
    requirements: z.string().min(10, 'Requirements must be at least 10 characters'),
    preferred_certifications: z.string().optional().or(z.literal('')),
    technical_competencies: z.string().min(10, 'Technical Competencies must be at least 10 characters'),
    what_we_offer: z.string().optional().or(z.literal('')),
    location: z.string().min(1, 'Location is required'),
    contract_type: z.enum(['FULL_TIME', 'PART_TIME', 'CONTRACT', 'FREELANCE', 'INTERNSHIP'], {
      error: 'Select a contract type',
    }),
    work_model: z.enum(['REMOTE', 'HYBRID', 'ONSITE']).optional().or(z.literal('')),
    work_location: z.enum(['LOCAL', 'INTERNATIONAL'], { error: 'Select a work location' }),
    salary_min: z.preprocess(
      (v) => (v === '' || v == null ? undefined : Number(v)),
      z.number().positive('Must be a positive number').optional()
    ),
    salary_max: z.preprocess(
      (v) => (v === '' || v == null ? undefined : Number(v)),
      z.number().positive('Must be a positive number').optional()
    ),
    seniority_level: z.enum(['JUNIOR', 'MID', 'SENIOR', 'LEAD', 'EXECUTIVE']).optional().or(z.literal('')),
    required_years_experience: z.preprocess(
      (v) => (v === '' || v == null ? undefined : Number(v)),
      z.number().int().min(0).max(50).optional()
    ),
    openings_count: z.preprocess(
      (v) => (v === '' || v == null ? 1 : Number(v)),
      z.number().int().min(1).max(999).default(1)
    ),
    application_deadline: z.string().optional().or(z.literal('')),
    required_skills: z.array(z.string()).optional(),
  })
  .refine(
    (data) => {
      if (data.salary_min != null && data.salary_max != null) {
        return data.salary_max >= data.salary_min
      }
      return true
    },
    { message: 'Salary max must be ≥ salary min', path: ['salary_max'] }
  )

const selectClass = cn(
  'flex h-10 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm',
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue',
  'disabled:cursor-not-allowed disabled:opacity-50'
)

const textareaClass = cn(
  'flex w-full rounded-md border border-border bg-surface px-3 py-2 text-sm',
  'placeholder:text-text-muted resize-y',
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue',
)

// ─── Skills tag input ─────────────────────────────────────────────────────────

function SkillsTagInput({ value = [], onChange }) {
  const [draft, setDraft] = React.useState('')

  const add = () => {
    const trimmed = draft.trim()
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed])
    }
    setDraft('')
  }

  const remove = (skill) => onChange(value.filter((s) => s !== skill))

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
          placeholder="e.g. Python, React, SQL…"
          className="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue"
        />
        <Button type="button" size="sm" variant="outline" onClick={add}>Add</Button>
      </div>
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((skill) => (
            <span
              key={skill}
              className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-brand-blue/10 text-brand-blue text-xs font-medium"
            >
              {skill}
              <button
                type="button"
                onClick={() => remove(skill)}
                aria-label={`Remove ${skill}`}
                className="hover:text-red-600 transition-colors"
              >
                <X size={11} />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Section divider ──────────────────────────────────────────────────────────

function SectionDivider({ title }) {
  return (
    <div className="pt-4 pb-1 border-t border-border">
      <p className="text-xs font-semibold text-text-muted uppercase tracking-wider">{title}</p>
    </div>
  )
}

/**
 * JobForm — shared create/edit form for job postings.
 *
 * Uses structured description fields (about_the_role, key_responsibilities,
 * requirements, preferred_certifications, technical_competencies, what_we_offer)
 * instead of a single generic description textarea.
 *
 * When draftKey is provided, form state is auto-saved to localStorage
 * and restored on mount — survives page reloads.
 */
export function JobForm({ defaultValues, onSubmit, loading = false, error = null, draftKey = null }) {
  const resolvedDefaults = {
    title: '',
    about_the_role: '',
    key_responsibilities: '',
    requirements: '',
    preferred_certifications: '',
    technical_competencies: '',
    what_we_offer: '',
    location: '',
    contract_type: undefined,
    work_model: '',
    work_location: undefined,
    salary_min: '',
    salary_max: '',
    seniority_level: '',
    required_years_experience: '',
    openings_count: 1,
    application_deadline: '',
    required_skills: [],
    ...defaultValues,
  }

  const initialValues = React.useMemo(() => {
    if (!draftKey) return resolvedDefaults
    try {
      const saved = localStorage.getItem(draftKey)
      if (saved) return { ...resolvedDefaults, ...JSON.parse(saved) }
    } catch { /* ignore corrupt draft */ }
    return resolvedDefaults
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const {
    register,
    handleSubmit,
    control,
    watch,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(jobSchema),
    defaultValues: initialValues,
  })

  const watchedValues = watch()
  React.useEffect(() => {
    if (!draftKey) return
    const timer = setTimeout(() => {
      try { localStorage.setItem(draftKey, JSON.stringify(watchedValues)) } catch { /* quota */ }
    }, 800)
    return () => clearTimeout(timer)
  }, [watchedValues, draftKey])

  const handleFormSubmit = (data) => {
    const cleaned = { ...data }
    if (cleaned.seniority_level === '') cleaned.seniority_level = null
    if (cleaned.work_model === '') cleaned.work_model = null
    if (cleaned.application_deadline === '') cleaned.application_deadline = null
    if (cleaned.preferred_certifications === '') cleaned.preferred_certifications = null
    if (cleaned.what_we_offer === '') cleaned.what_we_offer = null
    if (draftKey) { try { localStorage.removeItem(draftKey) } catch { /* ignore */ } }
    onSubmit(cleaned)
  }

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-5" noValidate>

      {/* Title */}
      <FormField>
        <Label htmlFor="title">Job title <span className="text-red-500">*</span></Label>
        <Input id="title" placeholder="e.g. Senior Software Engineer" {...register('title')} />
        <FormMessage>{errors.title?.message}</FormMessage>
      </FormField>

      <SectionDivider title="About the Role" />

      {/* About the Role */}
      <FormField>
        <Label htmlFor="about_the_role">
          About the Role <span className="text-red-500">*</span>
        </Label>
        <textarea
          id="about_the_role"
          rows={4}
          placeholder="Give an overview of the role and its purpose within the organisation…"
          className={textareaClass}
          {...register('about_the_role')}
        />
        <FormMessage>{errors.about_the_role?.message}</FormMessage>
      </FormField>

      {/* Key Responsibilities */}
      <FormField>
        <Label htmlFor="key_responsibilities">
          Key Responsibilities <span className="text-red-500">*</span>
        </Label>
        <textarea
          id="key_responsibilities"
          rows={5}
          placeholder="List the main duties and day-to-day responsibilities…"
          className={textareaClass}
          {...register('key_responsibilities')}
        />
        <FormMessage>{errors.key_responsibilities?.message}</FormMessage>
      </FormField>

      <SectionDivider title="Candidate Profile" />

      {/* Requirements */}
      <FormField>
        <Label htmlFor="requirements">
          Requirements <span className="text-red-500">*</span>
        </Label>
        <textarea
          id="requirements"
          rows={4}
          placeholder="Qualifications, experience, and must-have criteria…"
          className={textareaClass}
          {...register('requirements')}
        />
        <FormMessage>{errors.requirements?.message}</FormMessage>
      </FormField>

      {/* Preferred Certifications */}
      <FormField>
        <Label htmlFor="preferred_certifications">
          Preferred Certifications <span className="text-text-muted text-xs">(optional)</span>
        </Label>
        <textarea
          id="preferred_certifications"
          rows={2}
          placeholder="e.g. PMP, AWS Certified, CPA — nice-to-haves only…"
          className={textareaClass}
          {...register('preferred_certifications')}
        />
        <FormMessage>{errors.preferred_certifications?.message}</FormMessage>
      </FormField>

      {/* Technical Competencies */}
      <FormField>
        <Label htmlFor="technical_competencies">
          Technical Competencies <span className="text-red-500">*</span>
        </Label>
        <textarea
          id="technical_competencies"
          rows={3}
          placeholder="Specific tools, platforms, or technical skills required…"
          className={textareaClass}
          {...register('technical_competencies')}
        />
        <FormMessage>{errors.technical_competencies?.message}</FormMessage>
      </FormField>

      <SectionDivider title="Compensation & Benefits" />

      {/* What We Offer */}
      <FormField>
        <Label htmlFor="what_we_offer">
          What We Offer <span className="text-text-muted text-xs">(optional)</span>
        </Label>
        <textarea
          id="what_we_offer"
          rows={3}
          placeholder="Benefits, perks, culture highlights, growth opportunities…"
          className={textareaClass}
          {...register('what_we_offer')}
        />
        <FormMessage>{errors.what_we_offer?.message}</FormMessage>
      </FormField>

      <SectionDivider title="Job Details" />

      {/* Location */}
      <FormField>
        <Label htmlFor="location">Location <span className="text-red-500">*</span></Label>
        <Input id="location" placeholder="e.g. Lagos, Nigeria" {...register('location')} />
        <FormMessage>{errors.location?.message}</FormMessage>
      </FormField>

      {/* Contract type + Work model */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FormField>
          <Label htmlFor="contract_type">Contract type <span className="text-red-500">*</span></Label>
          <select id="contract_type" className={selectClass} {...register('contract_type')}>
            <option value="">Select contract type</option>
            <option value="FULL_TIME">Full Time</option>
            <option value="PART_TIME">Part Time</option>
            <option value="CONTRACT">Contract</option>
            <option value="FREELANCE">Freelance</option>
            <option value="INTERNSHIP">Internship</option>
          </select>
          <FormMessage>{errors.contract_type?.message}</FormMessage>
        </FormField>

        <FormField>
          <Label htmlFor="work_model">Work model</Label>
          <select id="work_model" className={selectClass} {...register('work_model')}>
            <option value="">Select work model</option>
            <option value="REMOTE">Remote</option>
            <option value="HYBRID">Hybrid</option>
            <option value="ONSITE">Onsite</option>
          </select>
          <FormMessage>{errors.work_model?.message}</FormMessage>
        </FormField>
      </div>

      {/* Work location */}
      <FormField>
        <Label>Work location <span className="text-red-500">*</span></Label>
        <Controller
          name="work_location"
          control={control}
          render={({ field }) => (
            <WorkLocationToggle value={field.value ?? null} onChange={field.onChange} />
          )}
        />
        <FormMessage>{errors.work_location?.message}</FormMessage>
      </FormField>

      {/* Seniority + Experience */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FormField>
          <Label htmlFor="seniority_level">Seniority level</Label>
          <select id="seniority_level" className={selectClass} {...register('seniority_level')}>
            <option value="">Select seniority</option>
            <option value="JUNIOR">Junior</option>
            <option value="MID">Mid-level</option>
            <option value="SENIOR">Senior</option>
            <option value="LEAD">Lead</option>
            <option value="EXECUTIVE">Executive</option>
          </select>
          <FormMessage>{errors.seniority_level?.message}</FormMessage>
        </FormField>

        <FormField>
          <Label htmlFor="required_years_experience">Min. years of experience</Label>
          <Input
            id="required_years_experience"
            type="number"
            min={0}
            max={50}
            placeholder="e.g. 3"
            {...register('required_years_experience')}
          />
          <FormMessage>{errors.required_years_experience?.message}</FormMessage>
        </FormField>
      </div>

      {/* Salary range */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FormField>
          <Label htmlFor="salary_min">Salary min (₦, optional)</Label>
          <Input id="salary_min" type="number" min={0} placeholder="e.g. 500000" {...register('salary_min')} />
          <FormMessage>{errors.salary_min?.message}</FormMessage>
        </FormField>

        <FormField>
          <Label htmlFor="salary_max">Salary max (₦, optional)</Label>
          <Input id="salary_max" type="number" min={0} placeholder="e.g. 900000" {...register('salary_max')} />
          <FormMessage>{errors.salary_max?.message}</FormMessage>
        </FormField>
      </div>

      {/* Required skills */}
      <FormField>
        <Label>Required skills</Label>
        <Controller
          name="required_skills"
          control={control}
          render={({ field }) => (
            <SkillsTagInput value={field.value ?? []} onChange={field.onChange} />
          )}
        />
        <p className="text-xs text-text-muted mt-1">Press Enter or click Add after each skill.</p>
        <FormMessage>{errors.required_skills?.message}</FormMessage>
      </FormField>

      {/* Openings + Deadline */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FormField>
          <Label htmlFor="openings_count">Number of openings</Label>
          <Input id="openings_count" type="number" min={1} max={999} placeholder="1" {...register('openings_count')} />
          <FormMessage>{errors.openings_count?.message}</FormMessage>
        </FormField>

        <FormField>
          <Label htmlFor="application_deadline">Application deadline</Label>
          <Input id="application_deadline" type="date" {...register('application_deadline')} />
          <FormMessage>{errors.application_deadline?.message}</FormMessage>
        </FormField>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <Button type="submit" className="w-full" size="lg" disabled={loading}>
        {loading ? <><Loader2 size={16} className="mr-2 animate-spin" />Saving job…</> : 'Save job'}
      </Button>

    </form>
  )
}
