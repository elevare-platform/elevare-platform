// How an AI interview finishes: either the interviewer decides it has covered the
// brief and calls the end_interview function, or the time limit runs out. These
// helpers keep that logic out of the component so it can be tested.

export const END_INTERVIEW_TOOL_NAME = 'end_interview'

// The interviewer may not end the interview in its first minute. A model that
// calls the function too early would cost the candidate their one real attempt.
export const MIN_SECONDS_BEFORE_AI_CAN_END = 60

// After the interviewer asks to end, wait for its goodbye to finish playing.
// The browser reports that with output_audio_buffer.stopped; if that event never
// arrives, end anyway after this long so the candidate is never left hanging.
export const END_AFTER_AUDIO_MS = 1000
export const END_AUDIO_FALLBACK_MS = 9000

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

/**
 * The moments in the interview where the interviewer is nudged, in seconds
 * before the end. The closing nudge goes out early enough (up to 35 seconds)
 * for a proper goodbye to finish before the hard cut-off, instead of the
 * session being cut mid-sentence.
 */
export function interviewTimeThresholds(totalSeconds) {
  return {
    totalSeconds,
    warn: clamp(totalSeconds * 0.15, 20, 90),
    closing: clamp(totalSeconds * 0.04, 12, 35),
    checkinInterval: clamp(totalSeconds * 0.25, 60, 180),
  }
}

/** The end_interview function call inside a Realtime response.done event, or null. */
export function findEndInterviewCall(message) {
  if (message?.type !== 'response.done') return null
  const output = message.response?.output ?? []
  return (
    output.find((item) => item?.type === 'function_call' && item?.name === END_INTERVIEW_TOOL_NAME)
    ?? null
  )
}

export function canAiEndNow(elapsedSeconds) {
  return elapsedSeconds >= MIN_SECONDS_BEFORE_AI_CAN_END
}

/**
 * Events that tell the interviewer "not yet" and make it continue. Sent when it
 * asks to end too early.
 */
export function tooEarlyToEndEvents(callId) {
  return [
    {
      type: 'conversation.item.create',
      item: {
        type: 'function_call_output',
        call_id: callId,
        output: JSON.stringify({
          ok: false,
          message: 'It is too early to end the interview. Continue with the next topic in the brief.',
        }),
      },
    },
    { type: 'response.create' },
  ]
}
