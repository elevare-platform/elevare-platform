import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { FormField, FormMessage } from '@/components/ui/form'

const schema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  email: z.string().email('Please enter a valid email address'),
  company: z.string().optional(),
  message: z.string().optional(),
})

export function ConsultationModal({ isOpen, onClose }) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitSuccessful },
    reset,
  } = useForm({
    resolver: zodResolver(schema),
  })

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  // Auto-close after success
  useEffect(() => {
    if (!isSubmitSuccessful) return
    const timer = setTimeout(() => {
      onClose()
      reset()
    }, 2000)
    return () => clearTimeout(timer)
  }, [isSubmitSuccessful, onClose, reset])

  const onSubmit = (data) => {
    console.log('Consultation form submitted:', data)
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

        <h2 id="consultation-modal-title" className="mb-4 text-xl font-semibold text-gray-900">
          Book a Consultation
        </h2>

        {isSubmitSuccessful ? (
          <p className="py-8 text-center text-green-600 font-medium" role="status">
            Thank you! We'll be in touch shortly.
          </p>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
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

            <Button type="submit" className="w-full">
              Send Request
            </Button>
          </form>
        )}
      </div>
    </div>
  )
}
