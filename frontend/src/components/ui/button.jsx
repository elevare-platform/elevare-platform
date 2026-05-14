import { cva } from 'class-variance-authority'
import { cn } from '@/lib/utils'

// cva defines the base styles and all variants in one place.
// Each variant maps to a set of Tailwind classes.
const buttonVariants = cva(
  // Base styles applied to every button
  'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-brand-blue text-white hover:bg-brand-blue-dark',
        outline: 'border border-brand-blue text-brand-blue bg-transparent hover:bg-brand-blue-light',
        ghost: 'text-brand-blue hover:bg-brand-blue-light',
        destructive: 'bg-red-600 text-white hover:bg-red-700',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-8 px-3 text-xs',
        lg: 'h-12 px-6 text-base',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

export function Button({ className, variant, size, ...props }) {
  return (
    <button
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  )
}
