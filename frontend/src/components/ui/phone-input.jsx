import { forwardRef } from 'react'
import PhoneInputBase from 'react-phone-number-input'
import flags from 'react-phone-number-input/flags'
import 'react-phone-number-input/style.css'
import { cn } from '@/lib/utils'

// Country-flag + national-number phone field, styled to match Input.
// Wraps react-phone-number-input, which manages its own controlled value
// (a full E.164 string), so it's used with react-hook-form's Controller
// rather than register().
export const PhoneInput = forwardRef(({ className, ...props }, ref) => {
  return (
    <PhoneInputBase
      ref={ref}
      international
      defaultCountry="NG"
      countryCallingCodeEditable={false}
      flags={flags}
      className={cn(
        'flex h-10 w-full items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm',
        'focus-within:ring-2 focus-within:ring-brand-blue',
        className
      )}
      numberInputProps={{
        className: cn(
          'flex-1 h-full bg-transparent outline-none text-sm',
          'placeholder:text-text-muted',
          'disabled:cursor-not-allowed disabled:opacity-50'
        ),
      }}
      {...props}
    />
  )
})

PhoneInput.displayName = 'PhoneInput'
