import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2 } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { JobForm } from '@/components/employer/JobForm'
import { Button } from '@/components/ui/button'
import api from '@/lib/api'

/**
 * PostJobPage — /employer/jobs/new
 * Protected: EMPLOYER role only (enforced via ProtectedRoute in App.jsx)
 * Requirements: 5.1, 5.2, 5.3, 5.7, 5.8, 5.9
 */
const DRAFT_KEY = 'elevare_job_draft'

export default function PostJobPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [profileIncomplete, setProfileIncomplete] = useState(false)
  const [kycRequired, setKycRequired] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  async function handleSubmit(data) {
    setLoading(true)
    setError(null)
    setProfileIncomplete(false)
    setKycRequired(false)

    try {
      await api.post('/api/v1/jobs', data)
      setSubmitted(true)
    } catch (err) {
      const code = err.response?.data?.code
      const body = err.response?.data
      if (code === 'PROFILE_INCOMPLETE') {
        setProfileIncomplete(true)
      } else if (code === 'KYC_REQUIRED') {
        setKycRequired(true)
      } else if (Array.isArray(body?.details)) {
        // Custom handler: { details: [{ field, message }] }
        setError(body.details.map((e) => `${e.field}: ${e.message}`).join(' · '))
      } else {
        setError(body?.message || 'Something went wrong. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-12">
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-text">Post a new job</h1>
            <p className="text-text-muted mt-1 text-sm">
              Fill in the details below to create a new job listing.
            </p>
          </div>

          {/* Profile incomplete — actionable banner */}
          {profileIncomplete && (
            <div className="mb-6 rounded-md border border-brand-amber bg-brand-amber/10 px-4 py-3 text-sm">
              <p className="font-medium text-amber-800">Your company profile is incomplete.</p>
              <p className="text-amber-700 mt-1">
                You need to complete your company profile before posting jobs.{' '}
                <a href="/employer/profile" className="underline font-medium hover:text-amber-900">
                  Complete your profile →
                </a>
              </p>
            </div>
          )}

          {/* KYC required — actionable banner */}
          {kycRequired && (
            <div className="mb-6 rounded-md border border-brand-amber bg-brand-amber/10 px-4 py-3 text-sm">
              <p className="font-medium text-amber-800">Company verification required.</p>
              <p className="text-amber-700 mt-1">
                You need to complete company verification (KYC) before posting jobs.{' '}
                <a href="/employer/verification" className="underline font-medium hover:text-amber-900">
                  Verify your company →
                </a>
              </p>
            </div>
          )}

          {/* Success state — pending approval notice */}
          {submitted ? (
            <div className="rounded-xl border border-green-200 bg-green-50 p-6 space-y-4">
              <div className="flex items-start gap-3">
                <CheckCircle2 size={22} className="text-green-600 flex-shrink-0 mt-0.5" />
                <div>
                  <h2 className="font-semibold text-green-900 text-base">Job submitted for review</h2>
                  <p className="text-sm text-green-800 mt-1 leading-relaxed">
                    Your listing has been created and is now pending admin approval.
                    You'll receive an email once it's approved — the email will include
                    a direct link to publish it and start receiving applications.
                  </p>
                </div>
              </div>
              <div className="flex gap-3 pt-1">
                <Button onClick={() => navigate('/employer/jobs')} size="sm">
                  View my jobs
                </Button>
                <Button variant="outline" size="sm" onClick={() => setSubmitted(false)}>
                  Post another job
                </Button>
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-surface p-6 sm:p-8">
              <JobForm
                onSubmit={handleSubmit}
                loading={loading}
                error={error}
                draftKey={DRAFT_KEY}
              />
            </div>
          )}
        </div>
      </main>

      <Footer />
    </div>
  )
}
