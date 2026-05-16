// Machine-readable codes the backend returns for restricted (but authenticated) accounts.
// Kept in a separate file to avoid circular imports between api.js and AuthContext.jsx.

export const ACCOUNT_STATUS_CODES = [
  'EMAIL_VERIFICATION_REQUIRED',
  'ACCOUNT_SUSPENDED',
  'ACCOUNT_BANNED',
  'ACCOUNT_DEACTIVATED',
]
