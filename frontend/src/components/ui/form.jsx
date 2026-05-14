import { cn } from '@/lib/utils'

// FormField wraps a label + input + error message as a unit
export function FormField({ className, ...props }) {
  return <div className={cn('space-y-1.5', className)} {...props} />
}

// FormMessage displays validation errors in red below an input
export function FormMessage({ className, children, ...props }) {
  if (!children) return null
  return (
    <p className={cn('text-xs font-medium text-red-600', className)} {...props}>
      {children}
    </p>
  )
}
