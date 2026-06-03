import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Eye, EyeOff, Loader2, Check, X, AlertCircle } from 'lucide-react'
import { useAuth, getPostAuthRedirect } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FormField, FormMessage } from '@/components/ui/form'
import api, { setAccessToken } from '@/lib/api'
import ehsLogo from '@/assets/ehs-logo.png'

// ─── Schema ───────────────────────────────────────────────────────────────────

const schema = z.object({
  first_name: z.string().min(2, 'First name must be at least 2 characters'),
  last_name: z.string().min(2, 'Last name must be at least 2 characters'),
  phone_number: z
    .string()
    .min(1, 'Phone number is required')
    .regex(/^\+?[0-9\s\-()]{7,15}$/, 'Enter a valid phone number'),
  password: z
    .string()
    .min(8, 'Password must be at least 8 characters')
    .regex(/[A-Z]/, 'Must contain an uppercase letter')
    .regex(/[0-9]/, 'Must contain a number')
    .regex(/[^A-Za-z0-9]/, 'Must contain a special character'),
  confirm_password: z.string(),
}).refine((d) => d.password === d.confirm_password, {
  message: 'Passwords do not match',
  path: ['confirm_password'],
})

const PASSWORD_RULES = [
  { label: 'At least 8 characters', test: (v) => v.length >= 8 },
  { label: 'One uppercase letter', test: (v) => /[A-Z]/.test(v) },
  { label: 'One number', test: (v) => /[0-9]/.test(v) },
  { label: 'One special character', test: (v) => /[^A-Za-z0-9]/.test(v) },
]

// ─── InviteAcceptPage ─────────────────────────────────────────────────────────

/**
 * Invite acceptance page — /invite/accept?token=<raw_token>
 * Reads the token from the URL, submits to POST /api/v1/auth/invite/accept,
 * then redirects based on the returned user's role and profile state.
 */
export default function InviteAcceptPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { updateUser } = useAuth()

  const token = searchParams.get('token')

  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [passwordValue, setPasswordValue] = useState('')
  const [serverError, setServerError] = useState(null)

  // Redirect immediately if no token in URL
  useEffect(() => {
    if (!token) navigate('/', { replace: true })
  }, [token, navigate])

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (values) => {
    setServerError(null)
    try {
      const { data } = await api.post(
        `/api/v1/auth/invite/accept?token=${encodeURIComponent(token)}`,
        {
          first_name: values.first_name,
          last_name: values.last_name,
          phone_number: values.phone_number,
          password: values.password,
          confirm_password: values.confirm_password,
        }
      )
      // Manually set auth state — same pattern as AuthContext.register
      setAccessToken(data.access_token)
      updateUser(data.user)
      navigate(getPostAuthRedirect(data.user), { replace: true })
    } catch (err) {
      const status = err.response?.status
      const data = err.response?.data
      if (status === 400 && data?.code === 'TOKEN_ALREADY_USED') {
        setServerError('This invite link has already been used. Please contact your administrator.')
      } else if (status === 400 && data?.code === 'VERIFICATION_TOKEN_EXPIRED') {
        setServerError('This invite link has expired. Please ask your administrator to resend the invite.')
      } else if (status === 401 || status === 400) {
        setServerError('This invite link is invalid. Please check the link or contact your administrator.')
      } else if (data?.message) {
        setServerError(data.message)
      } else {
        setServerError('Something went wrong. Please try again.')
      }
    }
  }

  if (!token) return null

  return (
    <div className="min-h-screen flex">
      {/* Brand panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-brand-blue flex-col justify-between p-12 relative overflow-hidden">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full border border-white/10" />
          <div className="absolute -top-12 -right-12 w-72 h-72 rounded-full border border-white/10" />
          <div className="absolute bottom-24 -left-24 w-80 h-80 rounded-full border border-white/10" />
        </div>
        <div className="relative z-10 flex items-center gap-3">
          <img src={ehsLogo} alt="Elevare Human Solutions" className="h-10 w-auto brightness-0 invert" />
        </div>
        <div className="relative z-10 space-y-4">
          <h1 className="text-4xl font-bold text-white leading-tight">
            You've been invited<br />to Elevare.
          </h1>
          <p className="text-white/70 text-lg leading-relaxed">
            Complete your account setup to get started.
          </p>
        </div>
        <p className="relative z-10 text-white/40 text-sm">
          © {new Date().getFullYear()} Elevare Human Solutions Ltd
        </p>
      </div>

      {/* Form panel */}
      <div className="flex-1 flex items-center justify-center p-6 bg-surface-muted">
        <div className="w-full max-w-md space-y-8">
          {/* Mobile logo */}
          <div className="flex items-center gap-3 lg:hidden">
            <img src={ehsLogo} alt="Elevare Human Solutions" className="h-9 w-auto" />
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-text">Accept your invitation</h2>
            <p className="text-text-muted text-sm">
              Set up your account details to complete the process.
            </p>
          </div>

          {/* Token error state — shown if token is clearly invalid before submit */}
          {serverError && serverError.includes('expired') && (
            <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
              <AlertCircle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-700">{serverError}</p>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <div className="grid grid-cols-2 gap-4">
              <FormField>
                <Label htmlFor="first_name">First name</Label>
                <Input id="first_name" placeholder="Ada" {...register('first_name')} />
                <FormMessage>{errors.first_name?.message}</FormMessage>
              </FormField>
              <FormField>
                <Label htmlFor="last_name">Last name</Label>
                <Input id="last_name" placeholder="Okafor" {...register('last_name')} />
                <FormMessage>{errors.last_name?.message}</FormMessage>
              </FormField>
            </div>

            <FormField>
              <Label htmlFor="phone_number">Phone number</Label>
              <Input
                id="phone_number"
                type="tel"
                placeholder="+234 800 000 0000"
                {...register('phone_number')}
              />
              <FormMessage>{errors.phone_number?.message}</FormMessage>
            </FormField>

            <FormField>
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Min. 8 characters"
                  className="pr-10"
                  {...register('password', {
                    onChange: (e) => setPasswordValue(e.target.value),
                  })}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {passwordValue.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {PASSWORD_RULES.map((rule) => {
                    const passed = rule.test(passwordValue)
                    return (
                      <li key={rule.label} className={`flex items-center gap-2 text-xs ${passed ? 'text-green-600' : 'text-text-muted'}`}>
                        {passed
                          ? <Check size={12} className="shrink-0" />
                          : <X size={12} className="shrink-0 text-red-400" />}
                        {rule.label}
                      </li>
                    )
                  })}
                </ul>
              )}
              <FormMessage>{errors.password?.message}</FormMessage>
            </FormField>

            <FormField>
              <Label htmlFor="confirm_password">Confirm password</Label>
              <div className="relative">
                <Input
                  id="confirm_password"
                  type={showConfirm ? 'text' : 'password'}
                  placeholder="Repeat your password"
                  className="pr-10"
                  {...register('confirm_password')}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text"
                  aria-label={showConfirm ? 'Hide password' : 'Show password'}
                >
                  {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              <FormMessage>{errors.confirm_password?.message}</FormMessage>
            </FormField>

            {serverError && !serverError.includes('expired') && (
              <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {serverError}
              </div>
            )}

            <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
              {isSubmitting ? (
                <><Loader2 size={16} className="mr-2 animate-spin" /> Setting up account…</>
              ) : (
                'Complete setup'
              )}
            </Button>
          </form>

          <p className="text-center text-sm text-text-muted">
            Already have an account?{' '}
            <Link to="/login" className="text-brand-blue font-medium hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
