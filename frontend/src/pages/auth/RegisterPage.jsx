import { useState, useCallback } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Loader2, Check, X, Briefcase, User } from 'lucide-react'
import { useAuth, getPostAuthRedirect } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FormField, FormMessage } from '@/components/ui/form'
import { cn } from '@/lib/utils'
import ehsLogo from '@/assets/ehs-logo.png'

// ─── Zod schema ───────────────────────────────────────────────────────────────

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

const PASSWORD_RULES = [
  { label: 'At least 8 characters', test: (v) => v.length >= 8 },
  { label: 'One uppercase letter', test: (v) => /[A-Z]/.test(v) },
  { label: 'One number', test: (v) => /[0-9]/.test(v) },
  { label: 'One special character (e.g. !@#$%)', test: (v) => /[^A-Za-z0-9]/.test(v) },
]

// ─── Shared brand panel ───────────────────────────────────────────────────────

function BrandPanel() {
  return (
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
  )
}

// ─── Step 1 — Role selection ──────────────────────────────────────────────────

function RoleCard({ role, selected, onClick }) {
  const isEmployer = role === 'EMPLOYER'
  return (
    <button
      type="button"
      onClick={() => onClick(role)}
      className={cn(
        'relative flex flex-col items-start gap-3 w-full rounded-xl border-2 p-5 text-left transition-all',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2',
        selected
          ? 'border-brand-blue bg-brand-blue/5'
          : 'border-border bg-surface hover:border-brand-blue/40 hover:bg-surface-muted'
      )}
      aria-pressed={selected}
    >
      {/* Icon */}
      <span
        className={cn(
          'flex items-center justify-center w-10 h-10 rounded-lg',
          selected
            ? isEmployer ? 'bg-brand-amber text-white' : 'bg-brand-blue text-white'
            : 'bg-surface-muted text-text-muted'
        )}
      >
        {isEmployer ? <Briefcase size={20} /> : <User size={20} />}
      </span>

      <div>
        <p className={cn('font-semibold text-sm', selected ? 'text-brand-blue' : 'text-text')}>
          {isEmployer ? 'Employer' : 'Candidate'}
        </p>
        <p className="text-xs text-text-muted mt-0.5 leading-relaxed">
          {isEmployer
            ? 'Post jobs and find talent for your company'
            : 'Browse jobs and build your career profile'}
        </p>
      </div>

      {/* Selected indicator */}
      {selected && (
        <span className="absolute top-3 right-3 w-5 h-5 rounded-full bg-brand-blue flex items-center justify-center">
          <Check size={11} className="text-white" strokeWidth={3} />
        </span>
      )}
    </button>
  )
}

function RoleStep({ onNext }) {
  const [selected, setSelected] = useState(null)

  return (
    <div className="w-full max-w-md space-y-8">
      <div className="flex items-center gap-3 lg:hidden">
        <img src={ehsLogo} alt="Elevare Human Solutions" width={104} height={36} className="h-9 w-auto" />
      </div>

      <div className="space-y-2">
        <h2 className="text-2xl font-bold text-text">Create your account</h2>
        <p className="text-text-muted text-sm">What brings you to Elevare?</p>
      </div>

      <div className="space-y-3">
        <RoleCard role="CANDIDATE" selected={selected === 'CANDIDATE'} onClick={setSelected} />
        <RoleCard role="EMPLOYER" selected={selected === 'EMPLOYER'} onClick={setSelected} />
      </div>

      <Button
        className="w-full"
        size="lg"
        disabled={!selected}
        onClick={() => onNext(selected)}
      >
        Continue
      </Button>

      <p className="text-center text-sm text-text-muted">
        Already have an account?{' '}
        <Link to="/login" className="text-brand-blue font-medium hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  )
}

// ─── Step 2 — Registration form ───────────────────────────────────────────────

function RegisterForm({ role, onBack }) {
  const { register: registerUser } = useAuth()
  const navigate = useNavigate()
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [serverError, setServerError] = useState(null)
  const [passwordValue, setPasswordValue] = useState('')

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (values) => {
    setServerError(null)
    try {
      const user = await registerUser({
        first_name: values.first_name,
        last_name: values.last_name,
        email: values.email,
        phone_number: values.phone_number,
        password: values.password,
        confirm_password: values.confirm_password,
        role,
      })
      navigate(getPostAuthRedirect(user), { replace: true })
    } catch (err) {
      const status = err.response?.status
      const data = err.response?.data
      if (status === 409) {
        setServerError('An account with this email or phone number already exists.')
      } else if (status === 422 && data?.details?.length) {
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
    <div className="w-full max-w-md space-y-8">
      <div className="flex items-center gap-3 lg:hidden">
        <img src={ehsLogo} alt="Elevare Human Solutions" width={104} height={36} className="h-9 w-auto" />
      </div>

      <div className="space-y-2">
        {/* Back + role badge */}
        <div className="flex items-center gap-3 mb-1">
          <button
            type="button"
            onClick={onBack}
            className="text-xs text-text-muted hover:text-text transition-colors"
            aria-label="Go back to account type selection"
          >
            ← Back
          </button>
          <span className={cn(
            'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
            role === 'EMPLOYER'
              ? 'bg-brand-amber/10 text-brand-amber'
              : 'bg-brand-blue/10 text-brand-blue'
          )}>
            {role === 'EMPLOYER' ? <Briefcase size={11} /> : <User size={11} />}
            {role === 'EMPLOYER' ? 'Employer account' : 'Candidate account'}
          </span>
        </div>
        <h2 className="text-2xl font-bold text-text">Your details</h2>
        <p className="text-text-muted text-sm">Fill in your information to get started.</p>
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

        {serverError && (
          <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {serverError}
          </div>
        )}

        <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
          {isSubmitting ? (
            <><Loader2 size={16} className="mr-2 animate-spin" /> Creating account…</>
          ) : (
            role === 'EMPLOYER' ? 'Create employer account' : 'Create account'
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
  )
}

// ─── RegisterPage ─────────────────────────────────────────────────────────────

export default function RegisterPage() {
  const [role, setRole] = useState(null)

  return (
    <div className="min-h-screen flex">
      <BrandPanel />

      <div className="flex-1 flex items-center justify-center p-6 bg-surface-muted">
        {role === null
          ? <RoleStep onNext={setRole} />
          : <RegisterForm role={role} onBack={() => setRole(null)} />
        }
      </div>
    </div>
  )
}
