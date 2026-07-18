import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { CheckCircle, XCircle, Loader2, Clock, AlertTriangle } from 'lucide-react'
import api from '@/lib/api'
import ehsLogo from '@/assets/ehs-logo.png'

const STATUS_CONTENT = {
  ACCEPTED: {
    icon: CheckCircle,
    iconClass: 'text-green-500',
    title: "You're connected!",
    body: "Thanks for accepting. The employer has been notified and can now see your details for this role.",
  },
  DECLINED: {
    icon: XCircle,
    iconClass: 'text-text-muted',
    title: 'Introduction declined',
    body: "No problem — the employer won't see your details for this role. Nothing further is needed from you.",
  },
  EXPIRED: {
    icon: Clock,
    iconClass: 'text-amber-500',
    title: 'This link has expired',
    body: 'This introduction request is no longer active. No action is needed on your end.',
  },
  already_responded: {
    icon: AlertTriangle,
    iconClass: 'text-amber-500',
    title: 'Already responded',
    body: "This link has already been used, so there's nothing more to do here.",
  },
}

export default function IntroductionResponsePage() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const action = params.get('action') // 'accept' | 'decline'

  const [status, setStatus] = useState('loading') // loading | ACCEPTED | DECLINED | EXPIRED | already_responded | error
  const [message, setMessage] = useState(null)

  useEffect(() => {
    if (!token || (action !== 'accept' && action !== 'decline')) {
      setStatus('error')
      return
    }

    let cancelled = false
    api.get(`/api/v1/public/introductions/${token}/${action}`)
      .then(({ data }) => {
        if (cancelled) return
        setMessage(data.message)
        setStatus(STATUS_CONTENT[data.status] ? data.status : 'already_responded')
      })
      .catch((err) => {
        if (cancelled) return
        setMessage(err?.response?.data?.message ?? null)
        setStatus('error')
      })

    return () => { cancelled = true }
  }, [token, action])

  const content = STATUS_CONTENT[status]

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-surface-muted px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <img src={ehsLogo} alt="Elevare" className="h-9 w-auto" />
        </div>

        <div className="bg-white rounded-2xl border border-border p-8 shadow-sm text-center space-y-4">
          {status === 'loading' && (
            <>
              <Loader2 size={40} className="mx-auto text-brand-blue animate-spin" />
              <p className="text-text font-medium">Processing your response…</p>
            </>
          )}

          {status === 'error' && (
            <>
              <XCircle size={40} className="mx-auto text-red-500" />
              <h1 className="text-xl font-bold text-text">Something went wrong</h1>
              <p className="text-sm text-text-muted">
                {message ?? 'This link is invalid. Please check the email and try again.'}
              </p>
            </>
          )}

          {content && status !== 'error' && (
            <>
              <content.icon size={40} className={`mx-auto ${content.iconClass}`} />
              <h1 className="text-xl font-bold text-text">{content.title}</h1>
              <p className="text-sm text-text-muted leading-relaxed">{message ?? content.body}</p>
            </>
          )}
        </div>

        <p className="text-center text-xs text-text-muted mt-6">
          <Link to="/" className="text-brand-blue hover:underline">Back to Elevare</Link>
        </p>
      </div>
    </div>
  )
}
