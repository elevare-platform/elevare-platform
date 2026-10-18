import { z } from 'zod'

// Code the server answers with when an account that still has a temporary
// password makes any request other than changing it.
export const PASSWORD_CHANGE_REQUIRED = 'PASSWORD_CHANGE_REQUIRED'

export function isPasswordChangeRequired(err) {
  return err?.response?.data?.code === PASSWORD_CHANGE_REQUIRED
}

// The same rules the server applies (backend auth/schemas.py
// validate_password_strength), so a mistake shows before a round trip. The
// server stays the authority.
export const PASSWORD_RULES = [
  'At least 8 characters',
  'One uppercase and one lowercase letter',
  'One digit',
  'One special character, such as ! @ # $ % & *',
]

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, 'Enter your current password'),
    new_password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .regex(/[A-Z]/, 'Password must contain an uppercase letter')
      .regex(/[a-z]/, 'Password must contain a lowercase letter')
      .regex(/\d/, 'Password must contain a digit')
      .regex(/[!@#$%^&*(),.?":{}|<>]/, 'Password must contain a special character'),
    confirm_password: z.string().min(1, 'Confirm your new password'),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    path: ['confirm_password'],
    message: 'Passwords do not match',
  })
  .refine((v) => v.new_password !== v.current_password, {
    path: ['new_password'],
    message: 'Choose a password different from the current one',
  })

// Maps a failed change-password request to a message and, where it belongs to a
// single field, the field to show it under. A wrong current password is a 400
// with its own code (never a 401, which the app reads as an expired session).
export function changePasswordError(err) {
  const status = err?.response?.status
  const code = err?.response?.data?.code
  if (code === 'INVALID_CURRENT_PASSWORD') {
    return { field: 'current_password', message: 'That is not your current password.' }
  }
  if (status === 422) {
    return { field: null, message: 'Please check the new password and try again.' }
  }
  if (status === 429) {
    return { field: null, message: 'Too many attempts. Please wait a minute and try again.' }
  }
  return { field: null, message: 'Something went wrong. Please try again.' }
}
