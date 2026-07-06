import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

// cn() merges Tailwind classes safely.
// clsx handles conditional logic, twMerge resolves conflicts (e.g. px-2 + px-4 → px-4)
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

// formatSalary formats a NGN salary integer into a human-readable string.
// ≥ 1,000,000 → ₦X.XM  (e.g. ₦1.2M)
// ≥ 1,000     → ₦X,XXX (e.g. ₦200,000)
// < 1,000     → ₦X     (e.g. ₦800)
// null/undefined → ''
// timeAgo returns a human-readable relative time string (e.g. "3 days ago").
// Returns null when the input is null/undefined.
export function timeAgo(dateString) {
  if (!dateString) return null
  const diff = Date.now() - new Date(dateString).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d ago`
  const weeks = Math.floor(days / 7)
  if (weeks < 5) return `${weeks}w ago`
  const months = Math.floor(days / 30)
  if (months < 12) return `${months}mo ago`
  return `${Math.floor(months / 12)}y ago`
}

export function formatSalary(value) {
  if (value == null) return ''
  if (value >= 1_000_000) {
    const m = value / 1_000_000
    // Show one decimal place only when needed (e.g. 1.2M not 2.0M)
    const formatted = Number.isInteger(m) ? `${m}` : `${parseFloat(m.toFixed(1))}`
    return `₦${formatted}M`
  }
  return `₦${value.toLocaleString('en-NG')}`
}
