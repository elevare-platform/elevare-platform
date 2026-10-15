import { describe, it, expect } from 'vitest'
import {
  canAiEndNow,
  findEndInterviewCall,
  interviewTimeThresholds,
  tooEarlyToEndEvents,
  MIN_SECONDS_BEFORE_AI_CAN_END,
} from './interviewEnding'

describe('findEndInterviewCall', () => {
  const endCall = { type: 'function_call', name: 'end_interview', call_id: 'call_1', arguments: '{}' }

  it('finds the call inside a response.done event, next to the spoken goodbye', () => {
    const message = {
      type: 'response.done',
      response: { output: [{ type: 'message', role: 'assistant' }, endCall] },
    }

    expect(findEndInterviewCall(message)).toBe(endCall)
  })

  it('ignores other functions, other events and malformed messages', () => {
    expect(
      findEndInterviewCall({
        type: 'response.done',
        response: { output: [{ type: 'function_call', name: 'something_else' }] },
      }),
    ).toBeNull()
    expect(findEndInterviewCall({ type: 'response.audio.delta' })).toBeNull()
    expect(findEndInterviewCall({ type: 'response.done' })).toBeNull()
    expect(findEndInterviewCall(null)).toBeNull()
  })
})

describe('canAiEndNow', () => {
  it('does not let the interviewer end the interview in its first minute', () => {
    expect(canAiEndNow(0)).toBe(false)
    expect(canAiEndNow(MIN_SECONDS_BEFORE_AI_CAN_END - 1)).toBe(false)
    expect(canAiEndNow(MIN_SECONDS_BEFORE_AI_CAN_END)).toBe(true)
    expect(canAiEndNow(600)).toBe(true)
  })
})

describe('tooEarlyToEndEvents', () => {
  it('answers the function call and asks the interviewer to carry on', () => {
    const [output, resume] = tooEarlyToEndEvents('call_9')

    expect(output.item).toMatchObject({ type: 'function_call_output', call_id: 'call_9' })
    expect(JSON.parse(output.item.output).ok).toBe(false)
    expect(resume).toEqual({ type: 'response.create' })
  })
})

describe('interviewTimeThresholds', () => {
  it('starts the closing nudge early enough for a full goodbye on a 15 minute interview', () => {
    const t = interviewTimeThresholds(15 * 60)

    expect(t.closing).toBe(35)
    expect(t.warn).toBe(90)
    expect(t.closing).toBeLessThan(t.warn)
  })

  it('stays in sensible bounds for very short interviews', () => {
    const t = interviewTimeThresholds(60)

    expect(t.closing).toBe(12)
    expect(t.warn).toBe(20)
  })
})
