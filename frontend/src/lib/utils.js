import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

// cn() merges Tailwind classes safely.
// clsx handles conditional logic, twMerge resolves conflicts (e.g. px-2 + px-4 → px-4)
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
