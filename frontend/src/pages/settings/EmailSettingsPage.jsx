import { useEffect, useState } from 'react'
import { Loader2, Mail } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

const ENDPOINT = '/api/v1/email-preferences/me'

/**
 * Turn emails from Elevare off (or back on) for the signed-in user's own address.
 * Available to every role. The same switch is what the Unsubscribe link in an email
 * flips, by address.
 */
export default function EmailSettingsPage() {
  const [preference, setPreference] = useState(null) // { email, emails_enabled }
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api.get(ENDPOINT)
      .then(({ data }) => { if (!cancelled) setPreference(data) })
      .catch(() => { if (!cancelled) setError('We could not load your email settings.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const toggle = async () => {
    setSaving(true)
    setError(null)
    try {
      const { data } = await api.put(ENDPOINT, { emails_enabled: !preference.emails_enabled })
      setPreference(data)
    } catch {
      setError('We could not save that change. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  const enabled = preference?.emails_enabled

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-12 space-y-8">
          <div>
            <h1 className="text-2xl font-bold text-text">Email settings</h1>
            <p className="text-sm text-text-muted mt-1">
              Choose whether Elevare sends you emails.
            </p>
          </div>

          {error && (
            <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex justify-center py-16">
              <Loader2 size={24} className="animate-spin text-brand-blue" />
            </div>
          ) : preference && (
            <section className="bg-white rounded-xl border border-border p-6">
              <div className="flex items-start justify-between gap-6">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Mail size={16} className="text-brand-blue" />
                    <h2 className="font-semibold text-text text-sm">Emails from Elevare</h2>
                  </div>
                  <p className="text-sm text-text-muted">
                    Sent to <span className="font-medium text-text break-all">{preference.email}</span>
                  </p>
                  <p className="text-sm text-text-muted mt-3">
                    {enabled
                      ? 'You receive application updates, introductions, interview invitations and reminders.'
                      : 'You will not receive these emails any more. Emails you need to use your account, like email verification, are still sent.'}
                  </p>
                </div>

                <button
                  type="button"
                  role="switch"
                  aria-checked={enabled}
                  aria-label="Receive emails from Elevare"
                  onClick={toggle}
                  disabled={saving}
                  className={cn(
                    'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2',
                    'disabled:opacity-60 cursor-pointer',
                    enabled ? 'bg-brand-blue' : 'bg-slate-300',
                  )}
                >
                  <span
                    className={cn(
                      'inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform',
                      enabled ? 'translate-x-5' : 'translate-x-0.5',
                    )}
                  />
                </button>
              </div>
            </section>
          )}
        </div>
      </main>

      <Footer />
    </div>
  )
}
