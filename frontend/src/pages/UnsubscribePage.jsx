import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CheckCircle, Loader2, MailX, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import api from '@/lib/api'
import ehsLogo from '@/assets/ehs-logo.png'

const BASE = '/api/v1/email-preferences'

/**
 * The page behind the "Unsubscribe" link in an email (no login needed).
 *
 * Opening it only SHOWS the choice; nothing changes until the button is pressed.
 * Email security scanners open every link in a message, so a link that unsubscribed
 * on open would switch off people who never asked.
 *
 * phase: loading | invalid | confirm (emails on, asking) | off | back_on | error
 */
export default function UnsubscribePage() {
  const [params] = useSearchParams()
  const token = params.get('token')

  const [phase, setPhase] = useState(token ? 'loading' : 'invalid')
  const [email, setEmail] = useState('')
  const [alreadyOff, setAlreadyOff] = useState(false)
  const [working, setWorking] = useState(false)

  useEffect(() => {
    if (!token) return undefined
    let cancelled = false
    api.get(`${BASE}/unsubscribe`, { params: { token } })
      .then(({ data }) => {
        if (cancelled) return
        setEmail(data.email)
        setAlreadyOff(!data.emails_enabled)
        setPhase(data.emails_enabled ? 'confirm' : 'off')
      })
      .catch((err) => {
        if (cancelled) return
        setPhase(err.response?.data?.code === 'INVALID_UNSUBSCRIBE_TOKEN' ? 'invalid' : 'error')
      })
    return () => { cancelled = true }
  }, [token])

  const change = async (action, nextPhase) => {
    setWorking(true)
    try {
      const { data } = await api.post(`${BASE}/${action}`, null, { params: { token } })
      setEmail(data.email)
      setAlreadyOff(false)
      setPhase(nextPhase)
    } catch {
      setPhase('error')
    } finally {
      setWorking(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-surface-muted px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <Link to="/"><img src={ehsLogo} alt="Elevare" className="h-9 w-auto" /></Link>
        </div>

        <div className="bg-white rounded-2xl border border-border p-8 shadow-sm text-center space-y-4">
          {phase === 'loading' && (
            <>
              <Loader2 size={40} className="mx-auto text-brand-blue animate-spin" />
              <p className="text-text font-medium">One moment…</p>
            </>
          )}

          {phase === 'confirm' && (
            <>
              <MailX size={40} className="mx-auto text-brand-blue" />
              <h1 className="text-xl font-bold text-text">Stop emails to {email}?</h1>
              <p className="text-sm text-text-muted">
                You will no longer receive emails from Elevare, such as application updates,
                introductions and interview invitations. We will still send the emails you need
                to use your account, like email verification.
              </p>
              <Button onClick={() => change('unsubscribe', 'off')} disabled={working} className="w-full">
                {working ? <Loader2 size={16} className="animate-spin" /> : 'Unsubscribe'}
              </Button>
              <Link to="/" className="block text-sm text-brand-blue hover:underline">
                No, keep my emails
              </Link>
            </>
          )}

          {phase === 'off' && (
            <>
              <CheckCircle size={40} className="mx-auto text-green-500" />
              <h1 className="text-xl font-bold text-text">
                {alreadyOff ? 'Emails are already off' : "You're unsubscribed"}
              </h1>
              <p className="text-sm text-text-muted">
                We will not send emails to {email} any more, except the ones you need to use your
                account, like email verification.
              </p>
              <p className="text-sm text-text-muted">Changed your mind?</p>
              <Button
                variant="outline"
                onClick={() => change('resubscribe', 'back_on')}
                disabled={working}
                className="w-full"
              >
                {working ? <Loader2 size={16} className="animate-spin" /> : 'Turn emails back on'}
              </Button>
            </>
          )}

          {phase === 'back_on' && (
            <>
              <CheckCircle size={40} className="mx-auto text-green-500" />
              <h1 className="text-xl font-bold text-text">Emails are back on</h1>
              <p className="text-sm text-text-muted">
                You will receive emails from Elevare at {email} again.
              </p>
            </>
          )}

          {phase === 'invalid' && (
            <>
              <XCircle size={40} className="mx-auto text-red-500" />
              <h1 className="text-xl font-bold text-text">This link is not valid</h1>
              <p className="text-sm text-text-muted">
                It may have been copied incompletely. If you have an Elevare account, you can
                turn emails off from your account settings.
              </p>
              <Link to="/settings/email" className="block text-sm text-brand-blue hover:underline">
                Open email settings
              </Link>
            </>
          )}

          {phase === 'error' && (
            <>
              <XCircle size={40} className="mx-auto text-red-500" />
              <h1 className="text-xl font-bold text-text">Something went wrong</h1>
              <p className="text-sm text-text-muted">
                We could not update your preference. Please try again in a moment.
              </p>
              <Button variant="outline" onClick={() => window.location.reload()} className="w-full">
                Try again
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
