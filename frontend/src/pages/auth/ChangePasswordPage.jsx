import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Loader2, LogOut } from 'lucide-react'
import { useAuth, getPostAuthRedirect } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FormField, FormMessage } from '@/components/ui/form'
import api from '@/lib/api'
import {
  PASSWORD_RULES,
  changePasswordError,
  changePasswordSchema,
} from '@/lib/passwordChange'
import ehsLogo from '@/assets/ehs-logo.png'

/**
 * Choose a new password - /change-password
 *
 * Any signed-in user can change their password here. For an account Elevare set
 * up with a temporary password it is the only page that works until the password
 * is changed: the server refuses every other request, and the route guard sends
 * the user here.
 */
export default function ChangePasswordPage() {
  const { user, authReady, completePasswordChange, logout } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState(null)

  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(changePasswordSchema),
  })

  if (!authReady) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-brand-blue border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />

  const forced = Boolean(user.must_change_password)

  const onSubmit = async (values) => {
    setServerError(null)
    try {
      const { data } = await api.post('/api/v1/auth/change-password', values)
      const updatedUser = await completePasswordChange(data)
      navigate(getPostAuthRedirect(updatedUser), { replace: true })
    } catch (err) {
      const { field, message } = changePasswordError(err)
      if (field) {
        setError(field, { message })
      } else {
        setServerError(message)
      }
    }
  }

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-surface-muted flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md space-y-6">
        <img src={ehsLogo} alt="Elevare Human Solutions" width={116} height={40} className="h-10 w-auto mx-auto" />

        <div className="bg-white rounded-xl border border-border p-6 shadow-sm space-y-5">
          <div>
            <h1 className="text-xl font-bold text-text">Choose a new password</h1>
            <p className="text-sm text-text-muted mt-1">
              {forced
                ? 'Your account was set up with a temporary password. Choose your own to continue.'
                : 'Enter your current password, then choose a new one.'}
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <FormField>
              <Label htmlFor="current_password">
                {forced ? 'Temporary password' : 'Current password'}
              </Label>
              <Input
                id="current_password"
                type="password"
                autoComplete="current-password"
                {...register('current_password')}
              />
              <FormMessage>{errors.current_password?.message}</FormMessage>
            </FormField>

            <FormField>
              <Label htmlFor="new_password">New password</Label>
              <Input
                id="new_password"
                type="password"
                autoComplete="new-password"
                {...register('new_password')}
              />
              <FormMessage>{errors.new_password?.message}</FormMessage>
            </FormField>

            <FormField>
              <Label htmlFor="confirm_password">Confirm new password</Label>
              <Input
                id="confirm_password"
                type="password"
                autoComplete="new-password"
                {...register('confirm_password')}
              />
              <FormMessage>{errors.confirm_password?.message}</FormMessage>
            </FormField>

            <ul className="text-xs text-text-muted list-disc pl-5 space-y-0.5">
              {PASSWORD_RULES.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ul>

            {serverError && (
              <div role="alert" className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {serverError}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? (
                <><Loader2 size={15} className="mr-2 animate-spin" /> Saving…</>
              ) : (
                'Save new password'
              )}
            </Button>
          </form>
        </div>

        {forced && (
          <button
            type="button"
            onClick={handleLogout}
            className="mx-auto flex items-center gap-1.5 text-sm text-text-muted hover:text-text"
          >
            <LogOut size={14} /> Sign out
          </button>
        )}
      </div>
    </div>
  )
}
