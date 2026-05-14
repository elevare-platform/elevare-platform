import { cn } from '@/lib/utils'

// A simple styled input. Spreads all native input props through.
// The `ref` forwarding is important — React Hook Form needs direct DOM access.
import { forwardRef } from 'react'

export const Input = forwardRef(({ className, type = 'text', ...props }, ref) => {
  return (
    <input
      type={type}
      ref={ref}
      className={cn(
        'flex h-10 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm',
        'placeholder:text-text-muted',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className
      )}
      {...props}
    />
  )
})

Input.displayName = 'Input'
