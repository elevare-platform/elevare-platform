import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Building2, Eye } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

function Skeleton({ className }) {
  return <div className={cn('animate-pulse bg-gray-200 rounded', className)} />
}

export default function ProfileViewsPage() {
  const [views, setViews] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.get('/api/v1/candidates/me/profile-views')
      .then(({ data }) => setViews(data?.items ?? data ?? []))
      .catch(() => setError('Failed to load profile views.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10">

          <Link
            to="/candidate/dashboard"
            className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text mb-6 transition-colors"
          >
            <ArrowLeft size={16} />
            Back to dashboard
          </Link>

          <div className="flex items-center gap-3 mb-6">
            <div className="w-9 h-9 rounded-lg bg-brand-blue/10 flex items-center justify-center flex-shrink-0">
              <Eye size={16} className="text-brand-blue" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-text">Profile Views</h1>
              <p className="text-xs text-text-muted mt-0.5">Employers who viewed your profile</p>
            </div>
          </div>

          {loading && (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="bg-white rounded-xl border border-border p-4 flex items-center gap-4">
                  <Skeleton className="w-10 h-10 rounded-lg flex-shrink-0" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-3.5 w-1/3" />
                    <Skeleton className="h-3 w-1/4" />
                  </div>
                  <Skeleton className="h-3 w-20" />
                </div>
              ))}
            </div>
          )}

          {!loading && error && (
            <p className="text-sm text-red-600" role="alert">{error}</p>
          )}

          {!loading && !error && views.length === 0 && (
            <div className="bg-white rounded-xl border border-border p-10 text-center">
              <Eye size={32} className="text-gray-300 mx-auto mb-3" />
              <p className="text-sm font-medium text-text">No profile views yet</p>
              <p className="text-xs text-text-muted mt-1">
                When employers view your profile, it will show up here.
              </p>
            </div>
          )}

          {!loading && !error && views.length > 0 && (
            <div className="space-y-3">
              {views.map((view) => (
                <div
                  key={view.id}
                  className="bg-white rounded-xl border border-border p-4 flex items-center gap-4"
                >
                  <span className="w-10 h-10 rounded-lg border border-border bg-surface-muted flex items-center justify-center flex-shrink-0">
                    {view.company_logo_url ? (
                      <img
                        src={view.company_logo_url}
                        alt={view.company_name ?? 'Company'}
                        className="w-full h-full rounded-lg object-contain"
                      />
                    ) : (
                      <Building2 size={16} className="text-text-muted" />
                    )}
                  </span>

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text truncate">
                      {view.company_name ?? 'An employer'}
                    </p>
                    {view.job_title && (
                      <p className="text-xs text-text-muted truncate mt-0.5">
                        Re: {view.job_title}
                      </p>
                    )}
                  </div>

                  <p className="text-xs text-text-muted flex-shrink-0">
                    {formatDate(view.viewed_at)}
                  </p>
                </div>
              ))}
            </div>
          )}

        </div>
      </main>

      <Footer />
    </div>
  )
}
