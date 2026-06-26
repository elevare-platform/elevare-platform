import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { storePostVerifyNext } from '@/pages/auth/VerifyEmailPage'
import { Eye, EyeOff, Loader2 } from 'lucide-react'
import { useAuth, getPostAuthRedirect } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FormField, FormMessage } from '@/components/ui/form'
import ehsLogo from '@/assets/ehs-logo.png'

const schema = z.object({
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
})

export default function LoginPage() {
  const { login, user, authReady } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [showPassword, setShowPassword] = useState(false)
  const [serverError, setServerError] = useState(null)

  const params = new URLSearchParams(location.search)
  const next = params.get('next') || location.state?.from?.pathname || null

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema),
  })

  // If already authenticated, redirect immediately
  useEffect(() => {
    if (authReady && user) {
      navigate(next || getPostAuthRedirect(user), { replace: true })
    }
  }, [authReady, user, next, navigate])

  const onSubmit = async (values) => {
    setServerError(null)
    try {
      const loggedInUser = await login(values.email, values.password)
      // If user logs in but is unverified, store next so verify page can redirect after
      if (loggedInUser.account_status === 'PENDING_VERIFICATION' && next) {
        storePostVerifyNext(next)
      }
      navigate(next || getPostAuthRedirect(loggedInUser), { replace: true })
    } catch (err) {
      const status = err.response?.status
      if (status === 401) {
        setServerError('Invalid email or password.')
      } else {
        setServerError('Something went wrong. Please try again.')
      }
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left — brand panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-brand-blue flex-col justify-between p-12 relative overflow-hidden">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full border border-white/10" />
          <div className="absolute -top-12 -right-12 w-72 h-72 rounded-full border border-white/10" />
          <div className="absolute bottom-24 -left-24 w-80 h-80 rounded-full border border-white/10" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full border border-white/5" />
        </div>

        <div className="relative z-10">
        <img src={ehsLogo} alt="Elevare Human Solutions" width={116} height={40} className="h-10 w-auto brightness-0 invert" />
        </div>

        <div className="relative z-10 space-y-6">
          <h1 className="text-4xl font-bold text-white leading-tight">
            Welcome back.<br />Let's get to work.
          </h1>
          <p className="text-white/70 text-lg leading-relaxed">
            Your next hire — or your next role — is waiting on the other side.
          </p>
        </div>

        <p className="relative z-10 text-white/40 text-sm">
          © {new Date().getFullYear()} Elevare Human Solutions Ltd
        </p>
      </div>

      {/* Right — form panel */}
      <div className="flex-1 flex items-center justify-center p-6 bg-surface-muted">
        <div className="w-full max-w-md space-y-8">
          <div className="flex items-center gap-3 lg:hidden">
            <img src={ehsLogo} alt="Elevare Human Solutions" width={104} height={36} className="h-9 w-auto" />
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-text">Sign in to your account</h2>
            <p className="text-text-muted text-sm">Enter your credentials to continue.</p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <FormField>
              <Label htmlFor="email">Email address</Label>
              <Input id="email" type="email" placeholder="ada@company.com" {...register('email')} />
              <FormMessage>{errors.email?.message}</FormMessage>
            </FormField>

            <FormField>
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Your password"
                  className="pr-10"
                  {...register('password')}
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
              <FormMessage>{errors.password?.message}</FormMessage>
            </FormField>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="remember"
                className="w-4 h-4 rounded border-border accent-brand-blue"
              />
              <Label htmlFor="remember" className="font-normal text-text-muted cursor-pointer">
                Remember me
              </Label>
            </div>

            {serverError && (
              <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {serverError}
              </div>
            )}

            <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
              {isSubmitting ? (
                <><Loader2 size={16} className="mr-2 animate-spin" /> Signing in…</>
              ) : (
                'Sign in'
              )}
            </Button>
          </form>

          <p className="text-center text-sm text-text-muted">
            Don't have an account?{' '}
            <Link
              to={next ? `/register?next=${next}` : '/register'}
              className="text-brand-blue font-medium hover:underline"
            >
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
