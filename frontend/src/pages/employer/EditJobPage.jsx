import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, CheckCircle2 } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { JobForm } from '@/components/employer/JobForm'
import api from '@/lib/api'

/**
 * EditJobPage — /employer/jobs/:id/edit
 * Loads the existing job, pre-fills JobForm, submits PATCH /api/v1/jobs/:id
 */
export default function EditJobPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [job, setJob] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [submitError, setSubmitError] = useState(null)
  const [loading, setLoading] = useState(false)

  // Fetch existing job data
  useEffect(() => {
    let cancelled = false
    api.get(`/api/v1/jobs/${id}`)
      .then(({ data }) => { if (!cancelled) setJob(data) })
      .catch(() => { if (!cancelled) setLoadError('Failed to load job. Please try again.') })
    return () => { cancelled = true }
  }, [id])

  const handleSubmit = async (data) => {
    setLoading(true)
    setSubmitError(null)
    try {
      await api.patch(`/api/v1/jobs/${id}`, data)
      navigate('/employer/jobs')
    } catch (err) {
      const body = err.response?.data
      if (Array.isArray(body?.details)) {
        // Custom handler: { details: [{ field, message }] }
        setSubmitError(body.details.map((e) => `${e.field}: ${e.message}`).join(' · '))
      } else {
        const msg = body?.message ?? body?.detail
        setSubmitError(typeof msg === 'string' ? msg : 'Something went wrong. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  // Map job fields to form defaults — normalise nulls to empty strings
  const defaultValues = job ? {
    title:                      job.title ?? '',
    description:                job.description ?? '',
    location:                   job.location ?? '',
    contract_type:              job.contract_type ?? undefined,
    work_model:                 job.work_model ?? '',
    work_location:              job.work_location ?? undefined,
    salary_min:                 job.salary_min != null ? String(job.salary_min) : '',
    salary_max:                 job.salary_max != null ? String(job.salary_max) : '',
    seniority_level:            job.seniority_level ?? '',
    required_years_experience:  job.required_years_experience != null ? String(job.required_years_experience) : '',
    openings_count:             job.openings_count ?? 1,
    application_deadline:       job.application_deadline ? job.application_deadline.slice(0, 10) : '',
    required_skills:            job.required_skills ?? [],
  } : undefined

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-12">

          <Link
            to="/employer/jobs"
            className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text mb-6 transition-colors"
          >
            <ArrowLeft size={14} />
            Back to jobs
          </Link>

          <div className="mb-8">
            <h1 className="text-2xl font-bold text-text">Edit job</h1>
            <p className="text-text-muted mt-1 text-sm">
              Update the details for this listing.
            </p>
          </div>

          {loadError && (
            <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 mb-6">
              {loadError}
            </div>
          )}

          {/* Skeleton while loading */}
          {!job && !loadError && (
            <div className="rounded-lg border border-border bg-surface p-6 sm:p-8 space-y-5 animate-pulse">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="space-y-2">
                  <div className="h-4 bg-gray-200 rounded w-24" />
                  <div className="h-10 bg-gray-200 rounded" />
                </div>
              ))}
            </div>
          )}

          {job && (
            <div className="rounded-lg border border-border bg-surface p-6 sm:p-8">
              <JobForm
                defaultValues={defaultValues}
                onSubmit={handleSubmit}
                loading={loading}
                error={submitError}
              />
            </div>
          )}

        </div>
      </main>

      <Footer />
    </div>
  )
}
