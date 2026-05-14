import { useState, useCallback } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Loader2, Check, X } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FormField, FormMessage } from '@/components/ui/form'

const schema = z.object({
  first_name: z.string().min(1, 'First name is required'),
  last_name: z.string().min(1, 'Last name is required'),
  email: z.string().email('Enter a valid email address'),
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

export default function RegisterPage() {
  const { register: registerUser } = useAuth()
  const navigate = useNavigate()
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [serverError, setServerError] = useState(null)
  const [passwordValue, setPasswordValue] = useState('')

  const passwordRules = [
    { label: 'At least 8 characters', test: (v) => v.length >= 8 },
    { label: 'One uppercase letter', test: (v) => /[A-Z]/.test(v) },
    { label: 'One number', test: (v) => /[0-9]/.test(v) },
    { label: 'One special character (e.g. !@#$%)', test: (v) => /[^A-Za-z0-9]/.test(v) },
  ]

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (values) => {
    setServerError(null)
    try {
      await registerUser({
        first_name: values.first_name,
        last_name: values.last_name,
        email: values.email,
        phone_number: values.phone_number,
        password: values.password,
        confirm_password: values.confirm_password,
      })
      navigate('/dashboard')
    } catch (err) {
      const status = err.response?.status
      const data = err.response?.data

      if (status === 409) {
        setServerError('An account with this email or phone number already exists.')
      } else if (status === 422 && data?.details?.length) {
        // Surface the first field-level error from the backend
        const first = data.details[0]
        setServerError(`${first.field.replace('_', ' ')}: ${first.message}`)
      } else if (data?.message) {
        setServerError(data.message)
      } else {
        setServerError('Something went wrong. Please try again.')
      }
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left — brand panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-brand-blue flex-col justify-between p-12 relative overflow-hidden">
        {/* Geometric decoration */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full border border-white/10" />
          <div className="absolute -top-12 -right-12 w-72 h-72 rounded-full border border-white/10" />
          <div className="absolute bottom-24 -left-24 w-80 h-80 rounded-full border border-white/10" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full border border-white/5" />
        </div>

        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-brand-amber flex items-center justify-center">
              <span className="text-white font-bold text-sm">E</span>
            </div>
            <span className="text-white font-semibold text-lg">Elevare</span>
          </div>
        </div>

        <div className="relative z-10 space-y-6">
          <h1 className="text-4xl font-bold text-white leading-tight">
            Connect talent<br />with opportunity.
          </h1>
          <p className="text-white/70 text-lg leading-relaxed">
            Join thousands of professionals and enterprises building careers and teams on Elevare.
          </p>
          <div className="flex gap-8">
            <div>
              <p className="text-3xl font-bold text-brand-amber">500+</p>
              <p className="text-white/60 text-sm">Companies hiring</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-brand-amber">12k+</p>
              <p className="text-white/60 text-sm">Active candidates</p>
            </div>
          </div>
        </div>

        <p className="relative z-10 text-white/40 text-sm">
          © {new Date().getFullYear()} Elevare Human Solutions Ltd
        </p>
      </div>

      {/* Right — form panel */}
      <div className="flex-1 flex items-center justify-center p-6 bg-surface-muted">
        <div className="w-full max-w-md space-y-8">
          {/* Mobile logo */}
          <div className="flex items-center gap-3 lg:hidden">
            <div className="w-8 h-8 rounded bg-brand-blue flex items-center justify-center">
              <span className="text-white font-bold text-sm">E</span>
            </div>
            <span className="text-text font-semibold text-lg">Elevare</span>
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-text">Create your account</h2>
            <p className="text-text-muted text-sm">Start your journey with Elevare today.</p>
          </div>

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
              <Label htmlFor="email">Email address</Label>
              <Input id="email" type="email" placeholder="ada@company.com" {...register('email')} />
              <FormMessage>{errors.email?.message}</FormMessage>
            </FormField>

            <FormField>
              <Label htmlFor="phone_number">Phone number</Label>
              <Input id="phone_number" type="tel" placeholder="+234 800 000 0000" {...register('phone_number')} />
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
              {/* Live password requirements — shown once user starts typing */}
              {passwordValue.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {passwordRules.map((rule) => {
                    const passed = rule.test(passwordValue)
                    return (
                      <li key={rule.label} className={`flex items-center gap-2 text-xs ${passed ? 'text-green-600' : 'text-text-muted'}`}>
                        {passed
                          ? <Check size={12} className="shrink-0" />
                          : <X size={12} className="shrink-0 text-red-400" />
                        }
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

            {serverError && (
              <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {serverError}
              </div>
            )}

            <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
              {isSubmitting ? (
                <><Loader2 size={16} className="mr-2 animate-spin" /> Creating account…</>
              ) : (
                'Create account'
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
