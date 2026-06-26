import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { CheckCircle, XCircle, Loader2, MailCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/context/AuthContext'
import api, { setAccessToken } from '@/lib/api'
import ehsLogo from '@/assets/ehs-logo.png'

const NEXT_KEY = 'elevare_post_verify_next'

/**
 * Called after registration to store the intended destination.
 * Used by VerifyEmailPage to redirect there after verification.
 */
export function storePostVerifyNext(next) {
  if (next) sessionStorage.setItem(NEXT_KEY, next)
}

function consumePostVerifyNext() {
  const val = sessionStorage.getItem(NEXT_KEY)
  if (val) sessionStorage.removeItem(NEXT_KEY)
  return val
}

export default function VerifyEmailPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { updateUser } = useAuth()

  const token = params.get('token')
  const nextFromUrl = params.get('next')

  const [status, setStatus] = useState('loading') // loading | success | error | no_token
  const [errorMsg, setErrorMsg] = useState(null)

  useEffect(() => {
    if (!token) { setStatus('no_token'); return }

    let cancelled = false
    api.post(`/api/v1/auth/verify-email?token=${token}`)
      .then(async () => {
        if (cancelled) return
        setStatus('success')

        // Refresh the user's auth state so account_status updates
        try {
          const { data: refreshData } = await api.post('/api/v1/auth/refresh')
          setAccessToken(refreshData.access_token)
          const { data: me } = await api.get('/api/v1/auth/me')
          updateUser(me)
        } catch { /* silent — they can re-login */ }

        // Redirect after 2 seconds
        const destination = nextFromUrl || consumePostVerifyNext() || '/candidate/dashboard'
        setTimeout(() => { if (!cancelled) navigate(destination, { replace: true }) }, 2000)
      })
      .catch((err) => {
        if (cancelled) return
        const code = err.response?.data?.code
        if (code === 'TOKEN_ALREADY_USED') {
          setErrorMsg('This verification link has already been used.')
        } else if (code === 'VERIFICATION_TOKEN_EXPIRED') {
          setErrorMsg('This verification link has expired. Request a new one below.')
        } else {
          setErrorMsg('This verification link is invalid or has expired.')
        }
        setStatus('error')
      })

    return () => { cancelled = true }
  }, [token])

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
              <p className="text-text font-medium">Verifying your email…</p>
            </>
          )}

          {status === 'success' && (
            <>
              <CheckCircle size={40} className="mx-auto text-green-500" />
              <h1 className="text-xl font-bold text-text">Email verified!</h1>
              <p className="text-sm text-text-muted">Your account is now active. Redirecting you…</p>
            </>
          )}

          {status === 'error' && (
            <>
              <XCircle size={40} className="mx-auto text-red-500" />
              <h1 className="text-xl font-bold text-text">Verification failed</h1>
              <p className="text-sm text-text-muted">{errorMsg}</p>
              <ResendSection />
            </>
          )}

          {status === 'no_token' && (
            <>
              <MailCheck size={40} className="mx-auto text-amber-500" />
              <h1 className="text-xl font-bold text-text">Check your inbox</h1>
              <p className="text-sm text-text-muted">
                We sent a verification link to your email. Click it to activate your account.
              </p>
              <ResendSection />
            </>
          )}
        </div>

        <p className="text-center text-xs text-text-muted mt-6">
          <Link to="/login" className="text-brand-blue hover:underline">Back to login</Link>
        </p>
      </div>
    </div>
  )
}

function ResendSection() {
  const [sent, setSent] = useState(false)
  const [sending, setSending] = useState(false)
  const [err, setErr] = useState(null)

  const handleResend = async () => {
    setSending(true)
    setErr(null)
    try {
      await api.post('/api/v1/auth/resend-verification-email')
      setSent(true)
    } catch {
      setErr('Could not resend. Make sure you are logged in and try again.')
    } finally {
      setSending(false)
    }
  }

  if (sent) return <p className="text-sm text-green-700">✓ Verification email sent. Check your inbox.</p>

  return (
    <div className="space-y-2">
      <Button onClick={handleResend} disabled={sending} variant="outline" className="w-full">
        {sending ? <><Loader2 size={14} className="animate-spin mr-2" />Sending…</> : 'Resend verification email'}
      </Button>
      {err && <p className="text-xs text-red-600">{err}</p>}
    </div>
  )
}
