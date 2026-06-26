import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeft, AlertCircle, CheckCircle, Plus, Trash2, Briefcase, GraduationCap, Award } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { SkillsInput } from '@/components/candidate/SkillsInput'
import { useCandidateProfile } from '@/hooks/useCandidateProfile'
import api from '@/lib/api'
import { trackEvent } from '@/lib/analytics'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getDirtyFields(initial, current) {
  const changed = {}
  for (const key of Object.keys(current)) {
    const a = initial[key]
    const b = current[key]
    const aStr = Array.isArray(a) ? JSON.stringify(a) : String(a ?? '')
    const bStr = Array.isArray(b) ? JSON.stringify(b) : String(b ?? '')
    if (aStr !== bStr) changed[key] = b
  }
  return changed
}

export function isDirty(initial, current) {
  return Object.keys(getDirtyFields(initial, current)).length > 0
}

const INPUT_CLS = 'w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue'
const CURRENCIES = ['NGN', 'USD', 'GBP', 'EUR', 'CAD', 'AUD', 'ZAR', 'GHS', 'KES']

// ─── Field wrapper ────────────────────────────────────────────────────────────

function Field({ label, htmlFor, hint, children, error }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-text">{label}</label>
      {children}
      {hint && !error && <p className="text-xs text-text-muted">{hint}</p>}
      {error && (
        <p role="alert" className="text-xs text-red-600 flex items-center gap-1">
          <AlertCircle size={12} aria-hidden="true" />{error}
        </p>
      )}
    </div>
  )
}

// ─── Section header ───────────────────────────────────────────────────────────

function SectionHeader({ icon: Icon, title, onAdd, addLabel }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <Icon size={16} className="text-brand-blue" />
        <h2 className="text-base font-semibold text-text">{title}</h2>
      </div>
      {onAdd && (
        <button type="button" onClick={onAdd}
          className="flex items-center gap-1 text-xs text-brand-blue hover:underline focus-visible:outline-none">
          <Plus size={13} />{addLabel ?? 'Add'}
        </button>
      )}
    </div>
  )
}

// ─── Work Experience form ─────────────────────────────────────────────────────

function WorkExperienceEntry({ entry, onDelete }) {
  return (
    <div className="rounded-lg border border-border bg-surface-muted p-4 space-y-1">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-text">{entry.job_title}</p>
          <p className="text-xs text-text-muted">{entry.company_name}</p>
          <p className="text-xs text-text-muted mt-0.5">
            {entry.start_date ?? '—'} → {entry.is_current ? 'Present' : (entry.end_date ?? '—')}
          </p>
        </div>
        <button type="button" onClick={() => onDelete(entry.id)}
          className="text-text-muted hover:text-red-500 transition-colors flex-shrink-0"
          aria-label="Delete work experience">
          <Trash2 size={14} />
        </button>
      </div>
      {entry.description && <p className="text-xs text-text-muted mt-1 line-clamp-2">{entry.description}</p>}
    </div>
  )
}

function WorkExperienceForm({ onSave, onCancel }) {
  const [form, setForm] = useState({
    company_name: '', job_title: '', description: '',
    start_date: '', end_date: '', is_current: false,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.company_name || !form.job_title) { setError('Company and job title are required.'); return }
    setSaving(true)
    try {
      const payload = {
        company_name: form.company_name,
        job_title: form.job_title,
        description: form.description || null,
        start_date: form.start_date || null,
        end_date: form.is_current ? null : (form.end_date || null),
        is_current: form.is_current,
      }
      const { data } = await api.post('/api/v1/candidates/me/work-experience', payload)
      onSave(data)
    } catch { setError('Failed to save. Try again.') }
    finally { setSaving(false) }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-brand-blue/30 bg-brand-blue/5 p-4 space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <input value={form.job_title} onChange={(e) => set('job_title', e.target.value)}
          placeholder="Job title *" className={INPUT_CLS} />
        <input value={form.company_name} onChange={(e) => set('company_name', e.target.value)}
          placeholder="Company *" className={INPUT_CLS} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <input type="date" value={form.start_date} onChange={(e) => set('start_date', e.target.value)}
          className={INPUT_CLS} aria-label="Start date" />
        <input type="date" value={form.end_date} onChange={(e) => set('end_date', e.target.value)}
          disabled={form.is_current} className={INPUT_CLS + (form.is_current ? ' opacity-40' : '')}
          aria-label="End date" />
      </div>
      <label className="flex items-center gap-2 text-sm text-text cursor-pointer">
        <input type="checkbox" checked={form.is_current} onChange={(e) => set('is_current', e.target.checked)} />
        Currently working here
      </label>
      <textarea value={form.description} onChange={(e) => set('description', e.target.value)}
        rows={2} placeholder="Description (optional)" className={INPUT_CLS + ' resize-none'} />
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-2 justify-end">
        <button type="button" onClick={onCancel}
          className="px-3 py-1.5 text-xs rounded-md border border-border hover:bg-surface-muted">Cancel</button>
        <button type="submit" disabled={saving}
          className="px-3 py-1.5 text-xs rounded-md bg-brand-blue text-white disabled:opacity-50">
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </form>
  )
}

// ─── Education form ───────────────────────────────────────────────────────────

function EducationEntry({ entry, onDelete }) {
  return (
    <div className="rounded-lg border border-border bg-surface-muted p-4 flex items-start justify-between gap-2">
      <div>
        <p className="text-sm font-medium text-text">{entry.degree} in {entry.field_of_study}</p>
        <p className="text-xs text-text-muted">{entry.institution_name}</p>
        {(entry.start_year || entry.end_year) && (
          <p className="text-xs text-text-muted mt-0.5">
            {entry.start_year ?? '—'} – {entry.end_year ?? 'Present'}
          </p>
        )}
      </div>
      <button type="button" onClick={() => onDelete(entry.id)}
        className="text-text-muted hover:text-red-500 transition-colors flex-shrink-0" aria-label="Delete education">
        <Trash2 size={14} />
      </button>
    </div>
  )
}

function EducationForm({ onSave, onCancel }) {
  const [form, setForm] = useState({
    institution_name: '', degree: '', field_of_study: '', start_year: '', end_year: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.institution_name || !form.degree || !form.field_of_study) {
      setError('Institution, degree, and field of study are required.'); return
    }
    setSaving(true)
    try {
      const { data } = await api.post('/api/v1/candidates/me/education', {
        institution_name: form.institution_name,
        degree: form.degree,
        field_of_study: form.field_of_study,
        start_year: form.start_year ? Number(form.start_year) : null,
        end_year: form.end_year ? Number(form.end_year) : null,
      })
      onSave(data)
    } catch { setError('Failed to save. Try again.') }
    finally { setSaving(false) }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-brand-blue/30 bg-brand-blue/5 p-4 space-y-3">
      <input value={form.institution_name} onChange={(e) => set('institution_name', e.target.value)}
        placeholder="Institution name *" className={INPUT_CLS} />
      <div className="grid grid-cols-2 gap-3">
        <input value={form.degree} onChange={(e) => set('degree', e.target.value)}
          placeholder="Degree *" className={INPUT_CLS} />
        <input value={form.field_of_study} onChange={(e) => set('field_of_study', e.target.value)}
          placeholder="Field of study *" className={INPUT_CLS} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <input type="number" value={form.start_year} onChange={(e) => set('start_year', e.target.value)}
          placeholder="Start year" className={INPUT_CLS} min={1950} max={2030} />
        <input type="number" value={form.end_year} onChange={(e) => set('end_year', e.target.value)}
          placeholder="End year" className={INPUT_CLS} min={1950} max={2030} />
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-2 justify-end">
        <button type="button" onClick={onCancel}
          className="px-3 py-1.5 text-xs rounded-md border border-border hover:bg-surface-muted">Cancel</button>
        <button type="submit" disabled={saving}
          className="px-3 py-1.5 text-xs rounded-md bg-brand-blue text-white disabled:opacity-50">
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </form>
  )
}

// ─── Certification form ───────────────────────────────────────────────────────

function CertificationEntry({ entry, onDelete }) {
  return (
    <div className="rounded-lg border border-border bg-surface-muted p-4 flex items-start justify-between gap-2">
      <div>
        <p className="text-sm font-medium text-text">{entry.name}</p>
        <p className="text-xs text-text-muted">{entry.issuing_organization}</p>
        {entry.issue_date && <p className="text-xs text-text-muted mt-0.5">Issued {entry.issue_date}</p>}
        {entry.credential_url && (
          <a href={entry.credential_url} target="_blank" rel="noopener noreferrer"
            className="text-xs text-brand-blue hover:underline mt-0.5 block">View credential</a>
        )}
      </div>
      <button type="button" onClick={() => onDelete(entry.id)}
        className="text-text-muted hover:text-red-500 transition-colors flex-shrink-0" aria-label="Delete certification">
        <Trash2 size={14} />
      </button>
    </div>
  )
}

function CertificationForm({ onSave, onCancel }) {
  const [form, setForm] = useState({
    name: '', issuing_organization: '', issue_date: '',
    expiration_date: '', credential_id: '', credential_url: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name || !form.issuing_organization) {
      setError('Name and issuing organization are required.'); return
    }
    setSaving(true)
    try {
      const { data } = await api.post('/api/v1/candidates/me/certifications', {
        name: form.name,
        issuing_organization: form.issuing_organization,
        issue_date: form.issue_date || null,
        expiration_date: form.expiration_date || null,
        credential_id: form.credential_id || null,
        credential_url: form.credential_url || null,
      })
      onSave(data)
    } catch { setError('Failed to save. Try again.') }
    finally { setSaving(false) }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-brand-blue/30 bg-brand-blue/5 p-4 space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <input value={form.name} onChange={(e) => set('name', e.target.value)}
          placeholder="Certification name *" className={INPUT_CLS} />
        <input value={form.issuing_organization} onChange={(e) => set('issuing_organization', e.target.value)}
          placeholder="Issuing organization *" className={INPUT_CLS} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-text-muted mb-1 block">Issue date</label>
          <input type="date" value={form.issue_date} onChange={(e) => set('issue_date', e.target.value)} className={INPUT_CLS} />
        </div>
        <div>
          <label className="text-xs text-text-muted mb-1 block">Expiry date</label>
          <input type="date" value={form.expiration_date} onChange={(e) => set('expiration_date', e.target.value)} className={INPUT_CLS} />
        </div>
      </div>
      <input value={form.credential_id} onChange={(e) => set('credential_id', e.target.value)}
        placeholder="Credential ID (optional)" className={INPUT_CLS} />
      <input value={form.credential_url} onChange={(e) => set('credential_url', e.target.value)}
        placeholder="Credential URL (optional)" className={INPUT_CLS} type="url" />
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-2 justify-end">
        <button type="button" onClick={onCancel}
          className="px-3 py-1.5 text-xs rounded-md border border-border hover:bg-surface-muted">Cancel</button>
        <button type="submit" disabled={saving}
          className="px-3 py-1.5 text-xs rounded-md bg-brand-blue text-white disabled:opacity-50">
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </form>
  )
}

// ─── CandidateProfilePage ─────────────────────────────────────────────────────

export default function CandidateProfilePage() {
  const { profile, loading, error, refetch } = useCandidateProfile()
  const navigate = useNavigate()
  const location = useLocation()
  const next = new URLSearchParams(location.search).get('next') || '/candidate/dashboard'

  const [values, setValues] = useState({
    bio: '', skills: [], years_of_experience: '', location: '',
    expected_salary: '', expected_currency: 'NGN', notice_period_days: '',
    linkedin_url: '', github_url: '', portfolio_url: '',
    open_to_relocation: false, visibility: 'APPLIED_ONLY',
  })
  const [initialValues, setInitialValues] = useState(null)

  // Sub-section lists
  const [workExperiences, setWorkExperiences] = useState([])
  const [educations, setEducations] = useState([])
  const [certifications, setCertifications] = useState([])

  // Form visibility toggles
  const [showWorkForm, setShowWorkForm] = useState(false)
  const [showEduForm, setShowEduForm] = useState(false)
  const [showCertForm, setShowCertForm] = useState(false)

  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [fieldErrors, setFieldErrors] = useState({})
  const [saveError, setSaveError] = useState(null)

  useEffect(() => {
    if (!profile) return
    const snapshot = {
      bio: profile.bio ?? '',
      skills: profile.skills ?? [],
      years_of_experience: profile.years_of_experience != null ? String(profile.years_of_experience) : '',
      location: profile.location ?? '',
      expected_salary: profile.expected_salary != null ? String(profile.expected_salary) : '',
      expected_currency: profile.expected_currency ?? 'NGN',
      notice_period_days: profile.notice_period_days != null ? String(profile.notice_period_days) : '',
      linkedin_url: profile.linkedin_url ?? '',
      github_url: profile.github_url ?? '',
      portfolio_url: profile.portfolio_url ?? '',
      open_to_relocation: profile.open_to_relocation ?? false,
      visibility: profile.visibility ?? 'APPLIED_ONLY',
    }
    setValues(snapshot)
    setInitialValues(snapshot)
    setWorkExperiences(profile.work_experiences ?? [])
    setEducations(profile.educations ?? [])
    setCertifications(profile.certifications ?? [])
  }, [profile])

  const dirty = initialValues ? isDirty(initialValues, values) : false

  const setField = useCallback((field, value) => {
    setValues((prev) => ({ ...prev, [field]: value }))
    setFieldErrors((prev) => { const n = { ...prev }; delete n[field]; return n })
    setSaveSuccess(false)
  }, [])

  const handleSave = useCallback(async (e) => {
    e.preventDefault()
    if (!dirty) return
    setSaving(true)
    setSaveSuccess(false)
    setSaveError(null)
    setFieldErrors({})

    const changed = getDirtyFields(initialValues, values)

    // Coerce numeric fields
    for (const f of ['years_of_experience', 'expected_salary', 'notice_period_days']) {
      if (f in changed) {
        const n = Number(changed[f])
        changed[f] = changed[f] === '' ? null : (Number.isNaN(n) ? null : n)
      }
    }
    // Clear empty strings to null
    for (const f of ['linkedin_url', 'github_url', 'portfolio_url']) {
      if (f in changed && changed[f] === '') changed[f] = null
    }

    try {
      await api.put('/api/v1/candidates/me', changed)
      setInitialValues({ ...values })
      setSaveSuccess(true)
      trackEvent('Profile', 'profile_complete')
      setTimeout(() => navigate(next, { replace: true }), 1200)
    } catch (err) {
      const detail = err?.response?.data?.detail
      if (Array.isArray(detail)) {
        const errs = {}
        detail.forEach((d) => { const f = d.loc?.[d.loc.length - 1]; if (f) errs[f] = d.msg })
        setFieldErrors(errs)
      } else {
        setSaveError(typeof detail === 'string' ? detail : (err.message ?? 'Failed to save profile.'))
      }
    } finally { setSaving(false) }
  }, [dirty, initialValues, values])

  // Delete handlers
  const handleDeleteWork = async (id) => {
    try {
      await api.delete(`/api/v1/candidates/me/work-experience/${id}`)
      setWorkExperiences((p) => p.filter((e) => e.id !== id))
    } catch { setSaveError('Failed to delete work experience.') }
  }

  const handleDeleteEducation = async (id) => {
    try {
      await api.delete(`/api/v1/candidates/me/education/${id}`)
      setEducations((p) => p.filter((e) => e.id !== id))
    } catch { setSaveError('Failed to delete education entry.') }
  }

  const handleDeleteCert = async (id) => {
    try {
      await api.delete(`/api/v1/candidates/me/certifications/${id}`)
      setCertifications((p) => p.filter((e) => e.id !== id))
    } catch { setSaveError('Failed to delete certification.') }
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />
      <main className="flex-1 pt-16">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-10 space-y-8">

          <Link to="/candidate/dashboard"
            className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-brand-blue transition-colors">
            <ArrowLeft size={14} aria-hidden="true" />Back to Career Hub
          </Link>

          <div>
            <h1 className="text-2xl font-bold text-text">Edit Profile</h1>
            <p className="text-text-muted text-sm mt-1">Keep your information accurate to improve your profile strength.</p>
          </div>

          {loading && (
            <div className="space-y-4 animate-pulse" aria-busy="true">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="space-y-2">
                  <div className="h-4 bg-slate-200 rounded w-28" />
                  <div className="h-10 bg-slate-200 rounded" />
                </div>
              ))}
            </div>
          )}

          {!loading && error && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-6 flex flex-col items-center gap-4 text-center">
              <AlertCircle size={32} className="text-red-400" />
              <div>
                <p className="font-semibold text-red-700">Failed to load your profile</p>
                <p className="text-sm text-red-600 mt-1">{error}</p>
              </div>
              <button type="button" onClick={refetch}
                className="rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50">
                Retry
              </button>
            </div>
          )}

          {!loading && !error && initialValues && (
            <form onSubmit={handleSave} noValidate className="space-y-6">

              {/* ── Basic info ── */}
              <section className="rounded-xl border border-border bg-surface p-6 space-y-5">
                <h2 className="text-base font-semibold text-text">Basic Information</h2>

                <Field label="About You" htmlFor="bio" error={fieldErrors.bio}>
                  <textarea id="bio" rows={4} value={values.bio}
                    onChange={(e) => setField('bio', e.target.value)}
                    placeholder="Tell recruiters about yourself…" className={INPUT_CLS + ' resize-y'} />
                </Field>

                <Field label="Your Skills" htmlFor="skills-input" error={fieldErrors.skills}>
                  <SkillsInput value={values.skills} onChange={(s) => setField('skills', s)} />
                </Field>

                <div className="grid grid-cols-2 gap-4">
                  <Field label="Years of Experience" htmlFor="years_of_experience" error={fieldErrors.years_of_experience}>
                    <input id="years_of_experience" type="number" min={0} max={50}
                      value={values.years_of_experience} onChange={(e) => setField('years_of_experience', e.target.value)}
                      placeholder="e.g. 3" className={INPUT_CLS} />
                  </Field>
                  <Field label="Location" htmlFor="location" error={fieldErrors.location}>
                    <input id="location" type="text" value={values.location}
                      onChange={(e) => setField('location', e.target.value)}
                      placeholder="e.g. Lagos, Nigeria" className={INPUT_CLS} />
                  </Field>
                </div>

                <Field label="Profile Visibility" htmlFor="visibility">
                  <select id="visibility" value={values.visibility}
                    onChange={(e) => setField('visibility', e.target.value)} className={INPUT_CLS}>
                    <option value="PUBLIC">Public — visible to all employers</option>
                    <option value="APPLIED_ONLY">Applied Only — visible to employers you've applied to</option>
                    <option value="PRIVATE">Private — hidden from all employers</option>
                  </select>
                </Field>

                <label className="flex items-center gap-2 text-sm text-text cursor-pointer">
                  <input type="checkbox" checked={values.open_to_relocation}
                    onChange={(e) => setField('open_to_relocation', e.target.checked)} />
                  Open to relocation
                </label>
              </section>

              {/* ── Additional details ── */}
              <section className="rounded-xl border border-border bg-surface p-6 space-y-5">
                <h2 className="text-base font-semibold text-text">Additional Details</h2>

                <div className="grid grid-cols-2 gap-4">
                  <Field label="Expected Salary" htmlFor="expected_salary" error={fieldErrors.expected_salary}>
                    <input id="expected_salary" type="number" min={0}
                      value={values.expected_salary} onChange={(e) => setField('expected_salary', e.target.value)}
                      placeholder="e.g. 500000" className={INPUT_CLS} />
                  </Field>
                  <Field label="Currency" htmlFor="expected_currency">
                    <select id="expected_currency" value={values.expected_currency}
                      onChange={(e) => setField('expected_currency', e.target.value)} className={INPUT_CLS}>
                      {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </Field>
                </div>

                <Field label="Notice Period (days)" htmlFor="notice_period_days" error={fieldErrors.notice_period_days}>
                  <input id="notice_period_days" type="number" min={0}
                    value={values.notice_period_days} onChange={(e) => setField('notice_period_days', e.target.value)}
                    placeholder="e.g. 30" className={INPUT_CLS} />
                </Field>

                <Field label="LinkedIn URL" htmlFor="linkedin_url" error={fieldErrors.linkedin_url}>
                  <input id="linkedin_url" type="url" value={values.linkedin_url}
                    onChange={(e) => setField('linkedin_url', e.target.value)}
                    placeholder="https://linkedin.com/in/yourname" className={INPUT_CLS} />
                </Field>

                <Field label="GitHub URL" htmlFor="github_url" error={fieldErrors.github_url}>
                  <input id="github_url" type="url" value={values.github_url}
                    onChange={(e) => setField('github_url', e.target.value)}
                    placeholder="https://github.com/yourname" className={INPUT_CLS} />
                </Field>

                <Field label="Portfolio URL" htmlFor="portfolio_url" error={fieldErrors.portfolio_url}>
                  <input id="portfolio_url" type="url" value={values.portfolio_url}
                    onChange={(e) => setField('portfolio_url', e.target.value)}
                    placeholder="https://yourportfolio.com" className={INPUT_CLS} />
                </Field>
              </section>

              {/* Save button + feedback */}
              {saveSuccess && (
                <div role="status" className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
                  <CheckCircle size={15} />Your profile has been updated.
                </div>
              )}
              {saveError && (
                <div role="alert" className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  <AlertCircle size={15} />{saveError}
                </div>
              )}
              <div className="flex justify-end">
                <button type="submit" disabled={!dirty || saving}
                  className="rounded-lg bg-brand-blue px-6 py-2.5 text-sm font-semibold text-white hover:bg-brand-blue/90 disabled:opacity-50 disabled:cursor-not-allowed">
                  {saving ? 'Saving…' : 'Save Profile'}
                </button>
              </div>

            </form>
          )}

          {/* ── Work Experience ── */}
          {!loading && !error && (
            <section className="rounded-xl border border-border bg-surface p-6 space-y-4">
              <SectionHeader icon={Briefcase} title="Work Experience"
                onAdd={() => setShowWorkForm(true)} addLabel="Add experience" />

              {workExperiences.map((e) => (
                <WorkExperienceEntry key={e.id} entry={e} onDelete={handleDeleteWork} />
              ))}
              {workExperiences.length === 0 && !showWorkForm && (
                <p className="text-sm text-text-muted">No work experience added yet.</p>
              )}
              {showWorkForm && (
                <WorkExperienceForm
                  onSave={(entry) => { setWorkExperiences((p) => [...p, entry]); setShowWorkForm(false) }}
                  onCancel={() => setShowWorkForm(false)}
                />
              )}
            </section>
          )}

          {/* ── Education ── */}
          {!loading && !error && (
            <section className="rounded-xl border border-border bg-surface p-6 space-y-4">
              <SectionHeader icon={GraduationCap} title="Education"
                onAdd={() => setShowEduForm(true)} addLabel="Add education" />

              {educations.map((e) => (
                <EducationEntry key={e.id} entry={e} onDelete={handleDeleteEducation} />
              ))}
              {educations.length === 0 && !showEduForm && (
                <p className="text-sm text-text-muted">No education entries added yet.</p>
              )}
              {showEduForm && (
                <EducationForm
                  onSave={(entry) => { setEducations((p) => [...p, entry]); setShowEduForm(false) }}
                  onCancel={() => setShowEduForm(false)}
                />
              )}
            </section>
          )}

          {/* ── Certifications ── */}
          {!loading && !error && (
            <section className="rounded-xl border border-border bg-surface p-6 space-y-4">
              <SectionHeader icon={Award} title="Certifications"
                onAdd={() => setShowCertForm(true)} addLabel="Add certification" />

              {certifications.map((e) => (
                <CertificationEntry key={e.id} entry={e} onDelete={handleDeleteCert} />
              ))}
              {certifications.length === 0 && !showCertForm && (
                <p className="text-sm text-text-muted">No certifications added yet.</p>
              )}
              {showCertForm && (
                <CertificationForm
                  onSave={(entry) => { setCertifications((p) => [...p, entry]); setShowCertForm(false) }}
                  onCancel={() => setShowCertForm(false)}
                />
              )}
            </section>
          )}

        </div>
      </main>
      <Footer />
    </div>
  )
}
