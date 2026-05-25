import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, AlertCircle, CheckCircle, Lock } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { SkillsInput } from '@/components/candidate/SkillsInput'
import { useCandidateProfile } from '@/hooks/useCandidateProfile'
import api from '@/lib/api'

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Compute the set of changed fields between initial and current values.
 * Arrays are compared by JSON serialisation (order-sensitive).
 * Returns an object containing only the keys whose values differ.
 *
 * Requirements: 11.4, 11.5, 11.6
 */
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

/**
 * Returns true if at least one field differs between initial and current.
 * Requirements: 11.4, 11.5
 */
export function isDirty(initial, current) {
  return Object.keys(getDirtyFields(initial, current)).length > 0
}

// ─── Sub-components ───────────────────────────────────────────────────────────

/** Labelled form field wrapper */
function Field({ label, htmlFor, children, error }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-text">
        {label}
      </label>
      {children}
      {error && (
        <p role="alert" className="text-xs text-red-600 flex items-center gap-1">
          <AlertCircle size={12} aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  )
}

/** Greyed-out "Coming Soon" locked field (Requirement 11.3) */
function LockedField({ label, placeholder = '' }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <label className="block text-sm font-medium text-text-muted">{label}</label>
        <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
          <Lock size={9} aria-hidden="true" />
          Coming Soon
        </span>
      </div>
      <input
        type="text"
        disabled
        placeholder={placeholder}
        aria-disabled="true"
        className="w-full rounded-md border border-border bg-slate-50 px-3 py-2 text-sm text-text-muted cursor-not-allowed opacity-60"
      />
    </div>
  )
}

// ─── CandidateProfilePage ─────────────────────────────────────────────────────

/**
 * Profile edit form for CANDIDATE users.
 *
 * Requirements: 11.1–11.9
 */
export default function CandidateProfilePage() {
  const { profile, loading, error, refetch } = useCandidateProfile()
  const navigate = useNavigate()

  // Editable form values — initialised from profile once loaded
  const [values, setValues] = useState({
    bio: '',
    skills: [],
    years_of_experience: '',
    location: '',
  })

  // Snapshot of values at load time — used for dirty-check
  const [initialValues, setInitialValues] = useState(null)

  // Submission state
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [fieldErrors, setFieldErrors] = useState({})
  const [saveError, setSaveError] = useState(null)

  // Requirement 11.1 — pre-fill form when profile loads
  useEffect(() => {
    if (!profile) return
    const snapshot = {
      bio: profile.bio ?? '',
      skills: profile.skills ?? [],
      years_of_experience: profile.years_of_experience != null ? String(profile.years_of_experience) : '',
      location: profile.location ?? '',
    }
    setValues(snapshot)
    setInitialValues(snapshot)
  }, [profile])

  // Requirement 11.4 / 11.5 — dirty-check
  const dirty = initialValues ? isDirty(initialValues, values) : false

  // Generic field setter
  const setField = useCallback((field, value) => {
    setValues((prev) => ({ ...prev, [field]: value }))
    // Clear field-level error on change
    setFieldErrors((prev) => {
      if (!prev[field]) return prev
      const next = { ...prev }
      delete next[field]
      return next
    })
    setSaveSuccess(false)
  }, [])

  // Requirement 11.6 — save only changed fields
  const handleSave = useCallback(async (e) => {
    e.preventDefault()
    if (!dirty) return

    setSaving(true)
    setSaveSuccess(false)
    setSaveError(null)
    setFieldErrors({})

    const changed = getDirtyFields(initialValues, values)

    // Coerce years_of_experience to number if present
    if ('years_of_experience' in changed) {
      const n = Number(changed.years_of_experience)
      changed.years_of_experience = Number.isNaN(n) ? null : n
    }

    try {
      await api.put('/api/v1/candidates/me', changed)
      // Update snapshot so dirty-check resets
      setInitialValues({ ...values })
      setSaveSuccess(true)
      // Redirect to Career Hub after a brief moment so the success banner is visible
      setTimeout(() => navigate('/candidate/dashboard'), 1200)
    } catch (err) {
      // Requirement 11.7 — field-level errors from response detail
      const detail = err?.response?.data?.detail
      if (Array.isArray(detail)) {
        // FastAPI validation errors: [{loc: [...], msg: '...'}]
        const errs = {}
        detail.forEach((d) => {
          const field = d.loc?.[d.loc.length - 1]
          if (field) errs[field] = d.msg
        })
        setFieldErrors(errs)
      } else {
        setSaveError(typeof detail === 'string' ? detail : (err.message ?? 'Failed to save profile.'))
      }
    } finally {
      setSaving(false)
    }
  }, [dirty, initialValues, values])

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-10 space-y-8">

          {/* Requirement 11.8 — back link */}
          <Link
            to="/candidate/dashboard"
            className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-brand-blue transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue rounded"
          >
            <ArrowLeft size={14} aria-hidden="true" />
            Back to Career Hub
          </Link>

          <div>
            <h1 className="text-2xl font-bold text-text">Edit Profile</h1>
            <p className="text-text-muted text-sm mt-1">
              Keep your information accurate to improve your profile strength.
            </p>
          </div>

          {/* Loading state */}
          {loading && (
            <div className="space-y-4 animate-pulse" aria-busy="true" aria-label="Loading profile">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="space-y-2">
                  <div className="h-4 bg-slate-200 rounded w-28" />
                  <div className="h-10 bg-slate-200 rounded" />
                </div>
              ))}
            </div>
          )}

          {/* Requirement 11.1 — error + retry on load failure */}
          {!loading && error && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-6 flex flex-col items-center gap-4 text-center">
              <AlertCircle size={32} className="text-red-400" aria-hidden="true" />
              <div>
                <p className="font-semibold text-red-700">Failed to load your profile</p>
                <p className="text-sm text-red-600 mt-1">{error}</p>
              </div>
              <button
                type="button"
                onClick={refetch}
                className="rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
              >
                Retry
              </button>
            </div>
          )}

          {/* Profile form — shown once profile is loaded */}
          {!loading && !error && initialValues && (
            <form onSubmit={handleSave} noValidate className="space-y-8">

              {/* ── Editable fields ── */}
              <section className="rounded-xl border border-border bg-surface p-6 space-y-6">
                <h2 className="text-base font-semibold text-text">Profile Information</h2>

                {/* Requirement 11.2 — bio textarea */}
                <Field label="About You" htmlFor="bio" error={fieldErrors.bio}>
                  <textarea
                    id="bio"
                    name="bio"
                    rows={4}
                    value={values.bio}
                    onChange={(e) => setField('bio', e.target.value)}
                    placeholder="Tell recruiters about yourself…"
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-text placeholder:text-text-muted resize-y focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue"
                  />
                </Field>

                {/* Requirement 11.2 / 11.9 — skills tag chip input */}
                <Field label="Your Skills" htmlFor="skills-input" error={fieldErrors.skills}>
                  <SkillsInput
                    value={values.skills}
                    onChange={(skills) => setField('skills', skills)}
                  />
                </Field>

                {/* Requirement 11.2 — years of experience */}
                <Field label="Years of Experience" htmlFor="years_of_experience" error={fieldErrors.years_of_experience}>
                  <input
                    id="years_of_experience"
                    name="years_of_experience"
                    type="number"
                    min={0}
                    max={50}
                    value={values.years_of_experience}
                    onChange={(e) => setField('years_of_experience', e.target.value)}
                    placeholder="e.g. 3"
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue"
                  />
                </Field>

                {/* Requirement 11.2 — location */}
                <Field label="Location" htmlFor="location" error={fieldErrors.location}>
                  <input
                    id="location"
                    name="location"
                    type="text"
                    value={values.location}
                    onChange={(e) => setField('location', e.target.value)}
                    placeholder="e.g. Lagos, Nigeria"
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue"
                  />
                </Field>
              </section>

              {/* ── Locked "Coming Soon" fields (Requirement 11.3) ── */}
              <section className="rounded-xl border border-border bg-surface p-6 space-y-6">
                <h2 className="text-base font-semibold text-text-muted">Additional Details</h2>

                <LockedField label="Expected Salary" placeholder="e.g. 500000" />
                <LockedField label="Expected Currency" placeholder="e.g. NGN" />
                <LockedField label="Notice Period (days)" placeholder="e.g. 30" />
                <LockedField label="LinkedIn URL" placeholder="https://linkedin.com/in/…" />
                <LockedField label="Profile Photo" placeholder="Upload coming soon" />
              </section>

              {/* ── Inline success banner (Requirement 11.6) ── */}
              {saveSuccess && (
                <div
                  role="status"
                  className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700"
                >
                  <CheckCircle size={15} aria-hidden="true" />
                  Your profile has been updated.
                </div>
              )}

              {/* ── Generic save error (Requirement 11.7) ── */}
              {saveError && (
                <div
                  role="alert"
                  className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
                >
                  <AlertCircle size={15} aria-hidden="true" />
                  {saveError}
                </div>
              )}

              {/* ── Save button (Requirements 11.4, 11.5) ── */}
              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={!dirty || saving}
                  aria-disabled={!dirty || saving}
                  className="rounded-lg bg-brand-blue px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-blue/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? 'Saving…' : 'Save Profile'}
                </button>
              </div>

            </form>
          )}

        </div>
      </main>

      <Footer />
    </div>
  )
}
