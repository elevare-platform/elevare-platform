import { describe, it, expect } from 'vitest'
import { interviewUnavailableMessage } from './interviewErrors'

describe('interviewUnavailableMessage', () => {
  it('returns the server message when the off switch is engaged', () => {
    const err = {
      response: {
        status: 503,
        data: { code: 'AI_INTERVIEWS_DISABLED', message: 'AI interviews are temporarily unavailable.' },
      },
    }

    expect(interviewUnavailableMessage(err)).toBe('AI interviews are temporarily unavailable.')
  })

  it('returns null for any other error', () => {
    expect(interviewUnavailableMessage({ response: { data: { code: 'VALIDATION_FAILED' } } })).toBeNull()
    expect(interviewUnavailableMessage(new Error('network'))).toBeNull()
    expect(interviewUnavailableMessage(undefined)).toBeNull()
  })
})
