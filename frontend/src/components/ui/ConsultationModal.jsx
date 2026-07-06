import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { X, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { FormField, FormMessage } from '@/components/ui/form'
import api from '@/lib/api'

const schema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  email: z.string().email('Please enter a valid email address'),
  company: z.string().optional(),
  message: z.string().optional(),
  // Honeypot — must stay empty; bots fill it, humans never see it
  website: z.string().optional(),
})

export function ConsultationModal({ isOpen, onClose }) {
  const [serverError, setServerError] = useState(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isSubmitSuccessful },
    reset,
  } = useForm({ resolver: zodResolver(schema) })

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [isOpen, onClose])

  // Auto-close 2s after success
  useEffect(() => {
    if (!isSubmitSuccessful) return
    const t = setTimeout(() => { onClose(); reset() }, 2000)
    return () => clearTimeout(t)
  }, [isSubmitSuccessful, onClose, reset])

  const onSubmit = async (data) => {
    setServerError(null)
    try {
      await api.post('/api/v1/contact', {
        name: data.name,
        email: data.email,
        company: data.company || undefined,
        // Pad message if empty so it passes the backend 20-char minimum
        message: data.message?.trim()
          ? data.message
          : 'Consultation request — no additional message provided.',
        inquiry_type: 'employer_inquiry',
        honeypot: data.website || '',  // hidden field — bots fill it, humans don't
      })
    } catch (err) {
      const detail = err.response?.data?.detail
      setServerError(
        typeof detail === 'string'
          ? detail
          : 'Something went wrong. Please try again or email us directly.'
      )
      throw err  // keeps isSubmitSuccessful false so the form stays visible
    }
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="consultation-modal-title"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="relative w-full max-w-md rounded-lg bg-white p-6 shadow-xl mx-4">
        <button
          type="button"
          onClick={onClose}
          aria-label="Close modal"
          className="absolute right-4 top-4 text-gray-400 hover:text-gray-600"
        >
          <X size={20} />
        </button>

        <h2 id="consultation-modal-title" className="mb-1 text-xl font-semibold text-gray-900 font-sans">
          Book a Consultation
        </h2>
        <p className="text-sm text-gray-500 mb-5">
          We'll reach out within 24 hours to schedule a call.
        </p>

        {isSubmitSuccessful ? (
          <p className="py-8 text-center text-green-600 font-medium" role="status">
            Thank you! We'll be in touch shortly.
          </p>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
            {/* Honeypot — visually hidden, only bots fill this */}
            <div aria-hidden="true" style={{ display: 'none' }}>
              <input
                type="text"
                tabIndex={-1}
                autoComplete="off"
                {...register('website')}
              />
            </div>

            <FormField>
              <label htmlFor="consultation-name" className="text-sm font-medium text-gray-700">
                Name <span aria-hidden="true">*</span>
              </label>
              <Input
                id="consultation-name"
                placeholder="Your name"
                aria-invalid={!!errors.name}
                aria-describedby={errors.name ? 'consultation-name-error' : undefined}
                {...register('name')}
              />
              <FormMessage id="consultation-name-error">{errors.name?.message}</FormMessage>
            </FormField>

            <FormField>
              <label htmlFor="consultation-email" className="text-sm font-medium text-gray-700">
                Email <span aria-hidden="true">*</span>
              </label>
              <Input
                id="consultation-email"
                type="email"
                placeholder="you@example.com"
                aria-invalid={!!errors.email}
                aria-describedby={errors.email ? 'consultation-email-error' : undefined}
                {...register('email')}
              />
              <FormMessage id="consultation-email-error">{errors.email?.message}</FormMessage>
            </FormField>

            <FormField>
              <label htmlFor="consultation-company" className="text-sm font-medium text-gray-700">
                Company
              </label>
              <Input
                id="consultation-company"
                placeholder="Your company (optional)"
                {...register('company')}
              />
            </FormField>

            <FormField>
              <label htmlFor="consultation-message" className="text-sm font-medium text-gray-700">
                Message
              </label>
              <textarea
                id="consultation-message"
                placeholder="How can we help? (optional)"
                rows={3}
                className="flex w-full rounded-md border border-border bg-surface px-3 py-2 text-sm placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue disabled:cursor-not-allowed disabled:opacity-50"
                {...register('message')}
              />
            </FormField>

            {serverError && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
                {serverError}
              </p>
            )}

            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting
                ? <><Loader2 size={14} className="animate-spin mr-2 inline" />Sending…</>
                : 'Send Request'}
            </Button>
          </form>
        )}
      </div>
    </div>
  )
}
