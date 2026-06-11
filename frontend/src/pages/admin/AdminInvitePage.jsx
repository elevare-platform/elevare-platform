import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, Copy, Check, RefreshCw, Send, LogOut } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FormField, FormMessage } from '@/components/ui/form'
import api from '@/lib/api'
import ehsLogo from '@/assets/ehs-logo.png'
import { cn } from '@/lib/utils'

// ─── Schema ───────────────────────────────────────────────────────────────────

const schema = z.object({
  email: z.string().email('Enter a valid email address'),
  role: z.enum(['EMPLOYER', 'ADMIN'], { required_error: 'Role is required' }),
})

// ─── Invite token display ─────────────────────────────────────────────────────

function InviteTokenCard({ token, email, onResend, resending }) {
  const [copied, setCopied] = useState(false)

  const inviteUrl = `${window.location.origin}/invite/accept?token=${token}`

  const handleCopy = async () => {
    await navigator.clipboard.writeText(inviteUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="rounded-xl border border-green-200 bg-green-50 p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-green-800">Invite created</p>
          <p className="text-xs text-green-700 mt-0.5">
            Invite link for <span className="font-medium">{email}</span>
          </p>
        </div>
        <span className="flex-shrink-0 w-7 h-7 rounded-full bg-green-200 flex items-center justify-center">
          <Check size={14} className="text-green-700" />
        </span>
      </div>

      {/* Invite URL */}
      <div className="space-y-1.5">
        <p className="text-xs font-medium text-green-800">Invite link</p>
        <div className="flex items-center gap-2">
          <code className="flex-1 min-w-0 block text-xs bg-white border border-green-200 rounded-lg px-3 py-2 text-green-900 truncate font-mono">
            {inviteUrl}
          </code>
          <button
            type="button"
            onClick={handleCopy}
            className={cn(
              'flex-shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors',
              copied
                ? 'bg-green-600 text-white'
                : 'bg-white border border-green-200 text-green-700 hover:bg-green-100'
            )}
            aria-label="Copy invite link"
          >
            {copied ? <Check size={13} /> : <Copy size={13} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      </div>

      {/* Raw token (stub mode convenience) */}
      <div className="space-y-1.5">
        <p className="text-xs font-medium text-green-800">Raw token</p>
        <code className="block text-xs bg-white border border-green-200 rounded-lg px-3 py-2 text-green-900 break-all font-mono">
          {token}
        </code>
      </div>

      {/* Resend */}
      <div className="pt-1 border-t border-green-200 flex items-center justify-between">
        <p className="text-xs text-green-700">Token expires in 3 days.</p>
        <button
          type="button"
          onClick={() => onResend(token)}
          disabled={resending}
          className="flex items-center gap-1.5 text-xs font-medium text-green-700 hover:text-green-900 disabled:opacity-60 transition-colors"
        >
          {resending
            ? <Loader2 size={12} className="animate-spin" />
            : <RefreshCw size={12} />}
          {resending ? 'Resending…' : 'Resend invite'}
        </button>
      </div>
    </div>
  )
}

// ─── AdminInvitePage ──────────────────────────────────────────────────────────

/**
 * Admin invite management page — /admin/invite
 * Protected: ADMIN role only.
 * Calls POST /api/v1/admin/employers/invite to generate an invite token.
 * Calls POST /api/v1/admin/employers/invite/{token}/resend to rotate a token.
 */
export default function AdminInvitePage() {
  const { user: authUser, logout: authLogout } = useAuth()
  const navigate = useNavigate()

  const [invites, setInvites] = useState([])
  const [serverError, setServerError] = useState(null)
  const [resendingToken, setResendingToken] = useState(null)

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { role: 'EMPLOYER' },
  })

  const onSubmit = async (values) => {
    setServerError(null)
    try {
      const { data } = await api.post('/api/v1/admin/employers/invite', {
        email: values.email,
        role: values.role,
      })
      // In stub mode the response is { invite_token: "..." }
      const token = data.invite_token ?? data.data?.invite_token
      if (token) {
        setInvites((prev) => [{ email: values.email, token }, ...prev])
      }
      reset({ role: 'EMPLOYER' })
    } catch (err) {
      const status = err.response?.status
      const msg = err.response?.data?.message ?? err.response?.data?.detail
      if (status === 409) {
        setServerError('A user with this email already exists on the platform.')
      } else {
        setServerError(msg || 'Something went wrong. Please try again.')
      }
    }
  }

  const handleResend = async (oldToken) => {
    setResendingToken(oldToken)
    try {
      const { data } = await api.post(
        `/api/v1/admin/employers/invite/${oldToken}/resend`
      )
      const newToken = data.invite_token ?? data.data?.invite_token
      if (newToken) {
        setInvites((prev) =>
          prev.map((inv) =>
            inv.token === oldToken ? { ...inv, token: newToken } : inv
          )
        )
      }
    } catch (err) {
      // Surface error inline on the card — don't wipe the whole page
      const msg = err.response?.data?.message ?? 'Failed to resend invite.'
      setServerError(msg)
    } finally {
      setResendingToken(null)
    }
  }

  const handleLogout = async () => {
    await authLogout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-surface-muted">
      {/* Header */}
      <header className="bg-white border-b border-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <img src={ehsLogo} alt="Elevare Human Solutions" width={104} height={36} className="h-9 w-auto" />
          <span className="text-text-muted text-sm">/ Admin</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-text-muted hidden sm:block">
            {authUser?.first_name} {authUser?.last_name}
          </span>
          <Button variant="outline" size="sm" onClick={handleLogout}>
            <LogOut size={14} className="mr-2" />
            Sign out
          </Button>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 sm:px-6 py-10 space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-text">Invite an employer</h1>
          <p className="text-text-muted text-sm mt-1">
            Generate an invite link for enterprise or managed employer accounts.
            The link expires after 3 days.
          </p>
        </div>

        {/* Invite form */}
        <div className="bg-white rounded-xl border border-border p-6 shadow-sm">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
            <FormField>
              <Label htmlFor="email">Email address</Label>
              <Input
                id="email"
                type="email"
                placeholder="employer@company.com"
                {...register('email')}
              />
              <FormMessage>{errors.email?.message}</FormMessage>
            </FormField>

            <FormField>
              <Label htmlFor="role">Account role</Label>
              <select
                id="role"
                className="flex h-10 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
                {...register('role')}
              >
                <option value="EMPLOYER">Employer</option>
                <option value="ADMIN">Admin</option>
              </select>
              <FormMessage>{errors.role?.message}</FormMessage>
            </FormField>

            {serverError && (
              <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {serverError}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? (
                <><Loader2 size={15} className="mr-2 animate-spin" /> Generating invite…</>
              ) : (
                <><Send size={15} className="mr-2" /> Generate invite link</>
              )}
            </Button>
          </form>
        </div>

        {/* Generated invites this session */}
        {invites.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-sm font-semibold text-text-muted uppercase tracking-wider">
              Generated this session
            </h2>
            {invites.map((inv) => (
              <InviteTokenCard
                key={inv.token}
                token={inv.token}
                email={inv.email}
                onResend={handleResend}
                resending={resendingToken === inv.token}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
