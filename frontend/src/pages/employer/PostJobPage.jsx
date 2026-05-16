import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { JobForm } from '@/components/employer/JobForm'
import api from '@/lib/api'

/**
 * PostJobPage — /employer/jobs/new
 * Protected: EMPLOYER role only (enforced via ProtectedRoute in App.jsx)
 * Requirements: 5.1, 5.2, 5.3, 5.7, 5.8, 5.9
 */
export default function PostJobPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [profileIncomplete, setProfileIncomplete] = useState(false)

  async function handleSubmit(data) {
    setLoading(true)
    setError(null)
    setProfileIncomplete(false)

    try {
      await api.post('/api/v1/jobs', data)
      navigate('/employer/jobs')
    } catch (err) {
      const status = err.response?.status
      const message = err.response?.data?.detail ?? err.response?.data?.message ?? ''

      // Req 5.8 — 403 with profile-incomplete message
      if (status === 403 && message.toLowerCase().includes('profile')) {
        setProfileIncomplete(true)
      } else {
        // Req 5.7 — other errors shown inline
        setError(message || 'Something went wrong. Please try again.')
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

          {/* Req 5.8 — amber banner for incomplete profile */}
          {profileIncomplete && (
            <div className="mb-6 rounded-md border border-brand-amber bg-brand-amber/10 px-4 py-3 text-sm text-brand-amber-dark font-medium">
              Complete your company profile before posting jobs.
            </div>
          )}

          <div className="rounded-lg border border-border bg-surface p-6 sm:p-8">
            <JobForm
              onSubmit={handleSubmit}
              loading={loading}
              error={error}
            />
          </div>
        </div>
      </main>

      <Footer />
    </div>
  )
}
