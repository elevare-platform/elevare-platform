import { cn } from '@/lib/utils'

// Card is split into composable sub-components.
// Usage: <Card><CardHeader><CardTitle>...</CardTitle></CardHeader><CardContent>...</CardContent></Card>

export function Card({ className, ...props }) {
  return (
    <div
      className={cn('rounded-lg border border-border bg-surface shadow-sm', className)}
      {...props}
    />
  )
}

export function CardHeader({ className, ...props }) {
  return <div className={cn('flex flex-col space-y-1.5 p-6', className)} {...props} />
}

export function CardTitle({ className, ...props }) {
  return <h2 className={cn('text-xl font-semibold text-text', className)} {...props} />
}

export function CardDescription({ className, ...props }) {
  return <p className={cn('text-sm text-text-muted', className)} {...props} />
}

export function CardContent({ className, ...props }) {
  return <div className={cn('p-6 pt-0', className)} {...props} />
}
