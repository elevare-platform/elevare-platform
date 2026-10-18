import { describe, it, expect } from 'vitest'
import {
  changePasswordError,
  changePasswordSchema,
  isPasswordChangeRequired,
} from './passwordChange'

const valid = {
  current_password: 'Temp-Pass-1!',
  new_password: 'Brand-New-Pass-2@',
  confirm_password: 'Brand-New-Pass-2@',
}

const firstMessage = (input) => {
  const result = changePasswordSchema.safeParse(input)
  return result.success ? null : result.error.issues[0].message
}

describe('changePasswordSchema', () => {
  it('accepts a strong new password that matches its confirmation', () => {
    expect(changePasswordSchema.safeParse(valid).success).toBe(true)
  })

  it.each([
    ['too short', 'Ab1!', 'at least 8 characters'],
    ['no uppercase', 'brand-new-pass-2@', 'uppercase'],
    ['no lowercase', 'BRAND-NEW-PASS-2@', 'lowercase'],
    ['no digit', 'Brand-New-Pass-@', 'digit'],
    ['no special character', 'BrandNewPass22', 'special'],
  ])('refuses a password with %s', (_label, password, expected) => {
    const message = firstMessage({
      ...valid,
      new_password: password,
      confirm_password: password,
    })
    expect(message).toContain(expected)
  })

  it('refuses a confirmation that differs', () => {
    expect(firstMessage({ ...valid, confirm_password: 'Different-Pass-3#' })).toBe(
      'Passwords do not match'
    )
  })

  it('refuses reusing the current password', () => {
    expect(
      firstMessage({
        current_password: 'Temp-Pass-1!',
        new_password: 'Temp-Pass-1!',
        confirm_password: 'Temp-Pass-1!',
      })
    ).toContain('different from the current one')
  })

  it('needs the current password', () => {
    expect(firstMessage({ ...valid, current_password: '' })).toBe(
      'Enter your current password'
    )
  })
})

describe('isPasswordChangeRequired', () => {
  it('recognises the server code and nothing else', () => {
    expect(isPasswordChangeRequired({ response: { data: { code: 'PASSWORD_CHANGE_REQUIRED' } } })).toBe(true)
    expect(isPasswordChangeRequired({ response: { data: { code: 'ACCOUNT_SUSPENDED' } } })).toBe(false)
    expect(isPasswordChangeRequired(new Error('network'))).toBe(false)
    expect(isPasswordChangeRequired(undefined)).toBe(false)
  })
})

describe('changePasswordError', () => {
  it('puts a wrong current password under that field', () => {
    expect(
      changePasswordError({ response: { status: 400, data: { code: 'INVALID_CURRENT_PASSWORD' } } })
    ).toEqual({ field: 'current_password', message: 'That is not your current password.' })
  })

  it('has a plain message for a rejected new password', () => {
    expect(changePasswordError({ response: { status: 422, data: {} } }).field).toBeNull()
  })

  it('tells the user to wait when rate limited', () => {
    expect(changePasswordError({ response: { status: 429, data: {} } }).message).toContain('wait')
  })

  it('has a generic message for anything else, including no response', () => {
    expect(changePasswordError(new Error('network')).message).toContain('Something went wrong')
  })
})
