import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, Building2 } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FormField, FormMessage } from '@/components/ui/form'
import api from '@/lib/api'

// ─── Schema ───────────────────────────────────────────────────────────────────

const schema = z.object({
  company_name: z.string().min(2, 'Company name must be at least 2 characters'),
  industry: z.string().min(1, 'Please select an industry'),
  company_size: z.string().min(1, 'Please select a company size'),
  website: z
    .string()
    .optional()
    .refine(
      (v) => !v || /^https?:\/\/.+/.test(v),
      'Website must start with http:// or https://'
    ),
  company_description: z.string().optional(),
})

const INDUSTRIES = [
  'Technology', 'Finance & Banking', 'Healthcare', 'Education',
  'Manufacturing', 'Retail & E-commerce', 'Media & Entertainment',
  'Consulting', 'Real Estate', 'Logistics & Supply Chain',
  'Energy & Utilities', 'Agriculture', 'Telecommunications', 'Other',
]

const COMPANY_SIZES = [
  { value: '1-10', label: '1–10 employees' },
  { value: '11-50', label: '11–50 employees' },
  { value: '51-200', label: '51–200 employees' },
  { value: '201-500', label: '201–500 employees' },
  { value: '501-1000', label: '501–1,000 employees' },
  { value: '1000+', label: '1,000+ employees' },
]

// ─── OnboardingPage ───────────────────────────────────────────────────────────

/**
 * Employer company profile onboarding — /employer/onboarding
 * Shown after employer registration when is_profile_complete is false.
 * Calls PATCH /api/v1/employer/profile (backend endpoint to be added).
 */
export default function OnboardingPage() {
  const { user, updateUser } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState(null)

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (values) => {
    setServerError(null)
    try {
      await api.patch('/api/v1/employer/profile', values)
      // Sync local auth state so ProtectedRoute doesn't redirect back here
      updateUser({ is_profile_complete: true })
      navigate('/employer/jobs', { replace: true })
    } catch (err) {
      const msg = err.response?.data?.message ?? err.response?.data?.detail
      setServerError(msg || 'Something went wrong. Please try again.')
    }
  }

  return (
    <div className="min-h-screen bg-surface-muted flex flex-col">
      {/* Minimal header */}
      <header className="bg-white border-b border-border px-6 py-4 flex items-center gap-3">
        <div className="w-7 h-7 rounded bg-brand-blue flex items-center justify-center">
          <span className="text-white font-bold text-xs">E</span>
        </div>
        <span className="font-semibold text-text">Elevare</span>
      </header>

      <main className="flex-1 flex items-start justify-center px-4 py-12">
        <div className="w-full max-w-lg">
          {/* Page header */}
          <div className="flex items-center gap-3 mb-8">
            <span className="flex items-center justify-center w-10 h-10 rounded-xl bg-brand-blue text-white flex-shrink-0">
              <Building2 size={20} />
            </span>
            <div>
              <h1 className="text-xl font-bold text-text">Set up your company profile</h1>
              <p className="text-sm text-text-muted mt-0.5">
                Hi {user?.first_name}, tell us about your company to start posting jobs.
              </p>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-border p-6 sm:p-8 shadow-sm">
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>

              <FormField>
                <Label htmlFor="company_name">Company name <span className="text-red-500">*</span></Label>
                <Input
                  id="company_name"
                  placeholder="Acme Corp"
                  {...register('company_name')}
                />
                <FormMessage>{errors.company_name?.message}</FormMessage>
              </FormField>

              <FormField>
                <Label htmlFor="industry">Industry <span className="text-red-500">*</span></Label>
                <select
                  id="industry"
                  className="flex h-10 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue disabled:opacity-50"
                  {...register('industry')}
                >
                  <option value="">Select an industry</option>
                  {INDUSTRIES.map((ind) => (
                    <option key={ind} value={ind}>{ind}</option>
                  ))}
                </select>
                <FormMessage>{errors.industry?.message}</FormMessage>
              </FormField>

              <FormField>
                <Label htmlFor="company_size">Company size <span className="text-red-500">*</span></Label>
                <select
                  id="company_size"
                  className="flex h-10 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue disabled:opacity-50"
                  {...register('company_size')}
                >
                  <option value="">Select company size</option>
                  {COMPANY_SIZES.map(({ value, label }) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
                <FormMessage>{errors.company_size?.message}</FormMessage>
              </FormField>

              <FormField>
                <Label htmlFor="website">Website <span className="text-text-muted font-normal">(optional)</span></Label>
                <Input
                  id="website"
                  type="url"
                  placeholder="https://yourcompany.com"
                  {...register('website')}
                />
                <FormMessage>{errors.website?.message}</FormMessage>
              </FormField>

              <FormField>
                <Label htmlFor="company_description">
                  About your company <span className="text-text-muted font-normal">(optional)</span>
                </Label>
                <textarea
                  id="company_description"
                  rows={3}
                  placeholder="Brief description of what your company does…"
                  className="flex w-full rounded-md border border-border bg-surface px-3 py-2 text-sm placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue disabled:opacity-50 resize-none"
                  {...register('company_description')}
                />
                <FormMessage>{errors.company_description?.message}</FormMessage>
              </FormField>

              {serverError && (
                <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                  {serverError}
                </div>
              )}

              <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
                {isSubmitting ? (
                  <><Loader2 size={16} className="mr-2 animate-spin" /> Saving…</>
                ) : (
                  'Complete setup'
                )}
              </Button>
            </form>
          </div>

          <p className="text-center text-xs text-text-muted mt-6">
            You can update your company profile later from your account settings.
          </p>
        </div>
      </main>
    </div>
  )
}
