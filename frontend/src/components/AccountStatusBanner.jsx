import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, MailCheck, ShieldOff, Ban, X, Loader2 } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

// ─── Banner config per account status ────────────────────────────────────────

function getBannerConfig(user) {
  const status = user?.account_status

  if (status === 'PENDING_VERIFICATION') {
    return {
      icon: MailCheck,
      colour: 'amber',
      title: 'Verify your email address',
      message: `We sent a verification link to ${user.email}. Check your inbox and click the link to activate your account.`,
      action: 'resend',
    }
  }

  if (status === 'SUSPENDED') {
    return {
      icon: ShieldOff,
      colour: 'orange',
      title: 'Account suspended',
      message: 'Your account has been temporarily suspended. Please contact support for assistance.',
      action: null,
    }
  }

  if (status === 'BANNED') {
    return {
      icon: Ban,
      colour: 'red',
      title: 'Account banned',
      message: 'Your account has been permanently banned due to a violation of our terms of service.',
      action: null,
    }
  }

  if (status === 'DEACTIVATED') {
    return {
      icon: AlertTriangle,
      colour: 'gray',
      title: 'Account deactivated',
      message: 'Your account has been deactivated. Contact support if you believe this is a mistake.',
      action: null,
    }
  }

  return null
}

const COLOUR_CLASSES = {
  amber: {
    wrapper: 'bg-amber-50 border-amber-200',
    icon: 'text-amber-500',
    title: 'text-amber-900',
    message: 'text-amber-800',
    button: 'text-amber-700 underline hover:text-amber-900',
    close: 'text-amber-400 hover:text-amber-600',
  },
  orange: {
    wrapper: 'bg-orange-50 border-orange-200',
    icon: 'text-orange-500',
    title: 'text-orange-900',
    message: 'text-orange-800',
    button: 'text-orange-700 underline hover:text-orange-900',
    close: 'text-orange-400 hover:text-orange-600',
  },
  red: {
    wrapper: 'bg-red-50 border-red-200',
    icon: 'text-red-500',
    title: 'text-red-900',
    message: 'text-red-800',
    button: 'text-red-700 underline hover:text-red-900',
    close: 'text-red-400 hover:text-red-600',
  },
  gray: {
    wrapper: 'bg-gray-50 border-gray-200',
    icon: 'text-gray-500',
    title: 'text-gray-900',
    message: 'text-gray-700',
    button: 'text-gray-600 underline hover:text-gray-900',
    close: 'text-gray-400 hover:text-gray-600',
  },
}

// ─── AccountStatusBanner ──────────────────────────────────────────────────────

/**
 * Persistent banner shown to authenticated users whose account is restricted.
 * Renders nothing for active accounts.
 */
export function AccountStatusBanner() {
  const { user, updateUser } = useAuth()
  const [dismissed, setDismissed] = useState(false)
  const [resending, setResending] = useState(false)
  const [resendDone, setResendDone] = useState(false)
  const [resendError, setResendError] = useState(null)

  const config = getBannerConfig(user)

  // Nothing to show for active accounts or if dismissed (non-critical statuses only)
  if (!config || dismissed) return null

  const c = COLOUR_CLASSES[config.colour]
  const Icon = config.icon

  const handleResend = async () => {
    setResending(true)
    setResendError(null)
    try {
      await api.post('/api/v1/auth/resend-verification-email')
      setResendDone(true)
    } catch {
      setResendError('Could not resend. Please try again.')
    } finally {
      setResending(false)
    }
  }

  // Only allow dismissing non-critical banners (suspended/banned/deactivated stay visible)
  const canDismiss = config.colour === 'amber'

  return (
    <div
      role="alert"
      aria-live="polite"
      className={cn(
        'border-b px-4 py-3',
        c.wrapper,
      )}
    >
      <div className="max-w-7xl mx-auto flex items-start gap-3">
        <Icon size={18} className={cn('flex-shrink-0 mt-0.5', c.icon)} aria-hidden="true" />

        <div className="flex-1 min-w-0">
          <p className={cn('text-sm font-semibold', c.title)}>{config.title}</p>
          <p className={cn('text-sm mt-0.5', c.message)}>{config.message}</p>

          {/* Resend action for PENDING_VERIFICATION */}
          {config.action === 'resend' && (
            <div className="mt-2">
              {resendDone ? (
                <p className={cn('text-sm font-medium', c.message)}>
                  ✓ Verification email sent. Check your inbox.
                </p>
              ) : (
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={resending}
                  className={cn('text-sm font-medium inline-flex items-center gap-1.5', c.button, 'disabled:opacity-60')}
                >
                  {resending && <Loader2 size={13} className="animate-spin" />}
                  {resending ? 'Sending…' : 'Resend verification email'}
                </button>
              )}
              {resendError && (
                <p className="text-sm text-red-600 mt-1">{resendError}</p>
              )}
            </div>
          )}
        </div>

        {canDismiss && (
          <button
            type="button"
            onClick={() => setDismissed(true)}
            className={cn('flex-shrink-0 p-0.5 rounded transition-colors', c.close)}
            aria-label="Dismiss notification"
          >
            <X size={16} />
          </button>
        )}
      </div>
    </div>
  )
}
