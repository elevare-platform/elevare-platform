import { useState, useRef, useCallback, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { AlertCircle, ArrowLeft, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import InterviewRules from '@/components/candidate/InterviewRules'
import { MAX_ATTEMPTS, uploadRecording, withRetry } from '@/lib/interviewUpload'
import {
  END_AFTER_AUDIO_MS,
  END_AUDIO_FALLBACK_MS,
  canAiEndNow,
  findEndInterviewCall,
  interviewTimeThresholds,
  tooEarlyToEndEvents,
} from '@/lib/interviewEnding'

const REALTIME_URL = 'https://api.openai.com/v1/realtime/calls'

// ─── Helpers ────────────────────────────────────────────────────────────────

// Returns a WebM type this browser can record, or null when it cannot record
// WebM at all (e.g. an older Safari). The backend stores and plays WebM only.
function pickRecorderMimeType() {
  if (typeof MediaRecorder === 'undefined') return null
  const candidates = [
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm',
  ]
  return candidates.find((type) => MediaRecorder.isTypeSupported?.(type)) ?? null
}

function formatTime(totalSeconds) {
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

// Sums matching numeric keys across two token_details objects (either may
// be null/undefined, e.g. on the first response.done of the session).
function mergeTokenDetails(a, b) {
  if (!b) return a
  if (!a) return { ...b }
  const merged = { ...a }
  for (const [key, value] of Object.entries(b)) {
    merged[key] = (merged[key] || 0) + (value || 0)
  }
  return merged
}

// Nudges the AI's own time-awareness via a hidden system message - distinct
// from the session's main `instructions`, meant for exactly this kind of
// mid-conversation update per the Realtime API's own docs.
function sendSystemMessage(dataChannel, text) {
  if (dataChannel?.readyState !== 'open') return
  dataChannel.send(JSON.stringify({
    type: 'conversation.item.create',
    item: {
      type: 'message',
      role: 'system',
      content: [{ type: 'input_text', text }],
    },
  }))
}

/**
 * InterviewFlow - the live AI video interview state machine: consent ->
 * connect (WebRTC direct to OpenAI) -> record -> upload -> done.
 *
 * Shared by the logged-in candidate route (application_id + auth) and the
 * public token route (emailed magic link, no login) - both just supply
 * different async functions for the three interview endpoints.
 */
export default function InterviewFlow({
  startSession,
  requestUploadUrl,
  completeUpload,
  requestReset,
  backTo,
  backLabel = 'Back',
  subtitle = null,
  doneAction = null,
  sessionStartCount = 0,
}) {
  // 'consent' | 'connecting' | 'active' | 'ending' | 'uploading' | 'upload_error' | 'done' | 'error'
  // 'upload_error' means the interview itself is over and only the recording
  // still has to reach us; the candidate retries that without a new session.
  const [phase, setPhase] = useState('consent')
  // The candidate has ticked "I have read these rules and I accept them" (docs/14).
  const [accepted, setAccepted] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  // 'sending' while the file goes up, then 'confirming' while we tell the server
  // it has arrived. Both count as "do not leave yet".
  const [uploadStep, setUploadStep] = useState('sending')
  const [uploadNote, setUploadNote] = useState(null)
  const [error, setError] = useState(null)
  const [errorCode, setErrorCode] = useState(null)
  const [resetRequestState, setResetRequestState] = useState('idle') // 'idle' | 'sending' | 'sent' | 'already_sent' | 'error'
  const [secondsLeft, setSecondsLeft] = useState(null)

  const videoRef = useRef(null)
  const remoteAudioRef = useRef(null)
  const streamRef = useRef(null)
  const pcRef = useRef(null)
  const dataChannelRef = useRef(null)
  const recorderRef = useRef(null)
  const chunksRef = useRef([])
  // The finished recording, kept in memory until the server confirms it has it,
  // so a failed upload can be retried without redoing the interview.
  const recordingBlobRef = useRef(null)
  // True once the file itself has reached storage, so a retry that only needs
  // to confirm completion does not upload the whole recording again.
  const fileUploadedRef = useRef(false)
  const audioCtxRef = useRef(null)
  const transcriptRef = useRef([]) // [{ role: 'AI' | 'Candidate', text }] in arrival order
  // Accumulated Realtime API usage across the whole session - summed across
  // every response.done event, since usage there is per-response, not
  // cumulative. Reported to the backend on completion for cost tracking -
  // the backend never sees the live connection to measure this itself.
  const usageRef = useRef({
    input_tokens: 0,
    output_tokens: 0,
    input_token_details: null,
    output_token_details: null,
  })
  const timerRef = useRef(null)
  const endingRef = useRef(false) // guards against double-teardown
  const expiresAtMsRef = useRef(null)
  const thresholdsRef = useRef({ totalSeconds: 0, warn: 0, closing: 0, checkinInterval: 0 })
  const checkinsFiredRef = useRef(0)
  const warnFiredRef = useRef(false)
  const closingFiredRef = useRef(false)
  // Set once the interviewer has asked to end; the interview closes when its
  // goodbye finishes playing (or after a fallback delay), not at once.
  const aiEndPendingRef = useRef(false)
  const aiEndTimerRef = useRef(null)

  useEffect(() => () => cleanup(), [])

  // From the moment the interview starts until the server has the recording, a
  // reload or closed tab loses it for good. Ask the browser to confirm first.
  const guardAgainstLeaving = ['active', 'ending', 'uploading', 'upload_error'].includes(phase)
  useEffect(() => {
    if (!guardAgainstLeaving) return undefined
    const warn = (event) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [guardAgainstLeaving])

  useEffect(() => {
    if (phase === 'active' && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current
    }
  }, [phase])

  function cleanup() {
    if (timerRef.current) clearInterval(timerRef.current)
    if (aiEndTimerRef.current) clearTimeout(aiEndTimerRef.current)
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      try { recorderRef.current.stop() } catch { /* already stopped */ }
    }
    if (pcRef.current) {
      try { pcRef.current.close() } catch { /* already closed */ }
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
    }
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      try { audioCtxRef.current.close() } catch { /* already closed */ }
    }
  }

  // Formats the accumulated Realtime transcript events into a labeled
  // dialogue string - "AI: ...\n\nCandidate: ...\n\n..." in the order they
  // arrived. This is what gets sent to the backend and, in turn, what the
  // scoring LLM reads - it needs both sides of the conversation, not just
  // the candidate's answers.
  function formatTranscript() {
    return transcriptRef.current
      .map(({ role, text }) => `${role}: ${text}`)
      .join('\n\n')
  }

  // Gets the recording to the server and confirms it. Safe to call again after a
  // failure: it keeps the recording in memory, skips the upload if the file
  // already arrived, and never starts a new interview session.
  const submitRecording = useCallback(async () => {
    setError(null)
    setUploadNote(null)
    setUploadStep('sending')
    setUploadProgress(fileUploadedRef.current ? 100 : 0)
    setPhase('uploading')
    try {
      if (!fileUploadedRef.current) {
        await uploadRecording({
          requestUploadUrl,
          blob: recordingBlobRef.current,
          contentType: 'video/webm',
          onProgress: setUploadProgress,
          onRetry: (attempt) => setUploadNote(
            `Your connection was interrupted. Trying again (attempt ${attempt + 1} of ${MAX_ATTEMPTS})…`
          ),
        })
        fileUploadedRef.current = true
      }
      // The file is in. Confirming it with the server is a separate, short
      // step; the screen says so, so nobody leaves at 100%.
      setUploadNote(null)
      setUploadProgress(100)
      setUploadStep('confirming')
      // Completing is safe to repeat: the server ignores a second call.
      await withRetry(() => completeUpload({
        transcript: formatTranscript(),
        realtimeUsage: usageRef.current,
      }))
      recordingBlobRef.current = null
      setPhase('done')
    } catch (err) {
      // The server says the file never reached storage: send it again.
      if (err?.response?.data?.code === 'RECORDING_NOT_RECEIVED') {
        fileUploadedRef.current = false
      }
      setError(
        err?.response?.data?.message
        || 'We could not upload your recording. Your connection may have dropped.'
      )
      setPhase('upload_error')
    }
  }, [requestUploadUrl, completeUpload])

  const endInterview = useCallback(async () => {
    if (endingRef.current) return
    endingRef.current = true
    if (timerRef.current) clearInterval(timerRef.current)
    if (aiEndTimerRef.current) clearTimeout(aiEndTimerRef.current)
    setPhase('ending')

    const recorder = recorderRef.current
    const recordingStopped = new Promise((resolve) => {
      if (!recorder || recorder.state === 'inactive') return resolve()
      recorder.onstop = resolve
      recorder.stop()
    })
    await recordingStopped

    if (pcRef.current) {
      try { pcRef.current.close() } catch { /* already closed */ }
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
    }

    recordingBlobRef.current = new Blob(chunksRef.current, {
      type: recorder?.mimeType || 'video/webm',
    })
    fileUploadedRef.current = false
    await submitRecording()
  }, [submitRecording])

  // The interviewer decided the brief is covered and called end_interview.
  const handleAiEndRequest = useCallback((call) => {
    if (aiEndPendingRef.current) return

    const { totalSeconds } = thresholdsRef.current
    const remaining = Math.max(0, Math.round((expiresAtMsRef.current - Date.now()) / 1000))
    const elapsed = totalSeconds ? totalSeconds - remaining : 0
    if (!canAiEndNow(elapsed)) {
      // Too early: a premature call must not cost the candidate their interview.
      // Answer the call and tell the interviewer to carry on.
      if (dataChannelRef.current?.readyState === 'open') {
        for (const event of tooEarlyToEndEvents(call.call_id)) {
          dataChannelRef.current.send(JSON.stringify(event))
        }
      }
      return
    }

    // Let the goodbye finish playing. If the browser never reports that, end anyway.
    aiEndPendingRef.current = true
    aiEndTimerRef.current = setTimeout(() => endInterview(), END_AUDIO_FALLBACK_MS)
  }, [endInterview])

  const handleAiAudioStopped = useCallback(() => {
    if (!aiEndPendingRef.current) return
    if (aiEndTimerRef.current) clearTimeout(aiEndTimerRef.current)
    aiEndTimerRef.current = setTimeout(() => endInterview(), END_AFTER_AUDIO_MS)
  }, [endInterview])

  const startInterview = useCallback(async () => {
    setError(null)
    setErrorCode(null)
    setResetRequestState('idle')
    recordingBlobRef.current = null
    fileUploadedRef.current = false
    aiEndPendingRef.current = false

    // Checked before startSession(): minting a session uses one of the
    // candidate's two attempts, so a browser that cannot record has to be
    // turned away before that happens, not after.
    if (!pickRecorderMimeType() || !navigator.mediaDevices?.getUserMedia) {
      setError(
        "This browser can't record the interview. Please open this link in the latest "
        + 'Chrome, Edge or Firefox, on a laptop or an Android phone.'
      )
      setPhase('error')
      return
    }

    setPhase('connecting')

    try {
      const session = await startSession()

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: true,
      })
      streamRef.current = stream

      const pc = new RTCPeerConnection()
      pcRef.current = pc

      const audioTrack = stream.getAudioTracks()[0]
      pc.addTrack(audioTrack, stream)

      // Mixes the candidate's mic and the AI's spoken audio into one
      // recorded track, so the employer's playback isn't silent whenever
      // the AI is "talking". The unmixed `audioTrack` above still goes to
      // OpenAI untouched - only the local recording is affected.
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)()
      audioCtxRef.current = audioCtx
      const mixDestination = audioCtx.createMediaStreamDestination()
      audioCtx.createMediaStreamSource(stream).connect(mixDestination)

      pc.ontrack = (event) => {
        if (remoteAudioRef.current) {
          remoteAudioRef.current.srcObject = event.streams[0]
        }
        audioCtx.createMediaStreamSource(event.streams[0]).connect(mixDestination)
      }

      const dataChannel = pc.createDataChannel('oai-events')
      dataChannelRef.current = dataChannel
      dataChannel.addEventListener('open', () => {
        dataChannel.send(JSON.stringify({ type: 'response.create' }))
      })
      // Captures both sides of the conversation as OpenAI transcribes them
      // live, so the saved transcript has real speaker labels instead of
      // being reconstructed (one-sided) from the recording afterward.
      dataChannel.addEventListener('message', (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'response.output_audio_transcript.done' && msg.transcript) {
            transcriptRef.current.push({ role: 'AI', text: msg.transcript })
          } else if (
            msg.type === 'conversation.item.input_audio_transcription.completed'
            && msg.transcript
          ) {
            transcriptRef.current.push({ role: 'Candidate', text: msg.transcript })
          } else if (msg.type === 'response.done' && msg.response?.usage) {
            // One response.done fires per AI turn - usage is per-response,
            // so sum across the whole session rather than overwrite.
            const u = msg.response.usage
            usageRef.current = {
              input_tokens: usageRef.current.input_tokens + (u.input_tokens || 0),
              output_tokens: usageRef.current.output_tokens + (u.output_tokens || 0),
              input_token_details: mergeTokenDetails(
                usageRef.current.input_token_details, u.input_token_details
              ),
              output_token_details: mergeTokenDetails(
                usageRef.current.output_token_details, u.output_token_details
              ),
            }
          }

          // The interviewer has covered the brief and says goodbye by calling
          // end_interview. Not part of the chain above: the same response.done
          // that carries the call also carries usage, which still has to be summed.
          const endCall = findEndInterviewCall(msg)
          if (endCall) handleAiEndRequest(endCall)
          if (msg.type === 'output_audio_buffer.stopped') handleAiAudioStopped()
        } catch {
          /* not a JSON event we care about */
        }
      })

      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)

      const sdpResponse = await fetch(REALTIME_URL, {
        method: 'POST',
        body: offer.sdp,
        headers: {
          Authorization: `Bearer ${session.client_secret}`,
          'Content-Type': 'application/sdp',
        },
      })
      if (!sdpResponse.ok) {
        throw new Error('Could not connect to the interviewer. Please try again.')
      }
      const answerSdp = await sdpResponse.text()
      await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp })

      const mimeType = pickRecorderMimeType()
      chunksRef.current = []
      const recordingStream = new MediaStream([
        stream.getVideoTracks()[0],
        mixDestination.stream.getAudioTracks()[0],
      ])
      const recorder = new MediaRecorder(recordingStream, { mimeType })
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.start(1000)
      recorderRef.current = recorder

      const totalSeconds = session.max_duration_minutes * 60
      // Anchored to the session's real expiry, not re-derived locally -
      // the OpenAI token's own expires_after clock started earlier (when
      // it was minted, before getUserMedia/WebRTC negotiation), so this
      // is the only way the countdown can't drift past what the token
      // actually allows.
      expiresAtMsRef.current = new Date(session.expires_at).getTime()
      thresholdsRef.current = interviewTimeThresholds(totalSeconds)
      checkinsFiredRef.current = 0
      warnFiredRef.current = false
      closingFiredRef.current = false

      setSecondsLeft(Math.max(0, Math.round((expiresAtMsRef.current - Date.now()) / 1000)))
      timerRef.current = setInterval(() => {
        const remaining = Math.max(0, Math.round((expiresAtMsRef.current - Date.now()) / 1000))
        setSecondsLeft(remaining)

        const { totalSeconds: total, warn, closing, checkinInterval } = thresholdsRef.current
        const elapsed = total - remaining

        if (
          total >= 90
          && remaining > warn
          && elapsed >= checkinInterval * (checkinsFiredRef.current + 1)
        ) {
          checkinsFiredRef.current += 1
          sendSystemMessage(
            dataChannelRef.current,
            `Time check: about ${formatTime(remaining)} left in this interview. `
            + 'If you have already covered everything in the brief, close the interview now. '
            + 'Do not ask more questions just to use the time.'
          )
        }

        if (!warnFiredRef.current && remaining <= warn) {
          warnFiredRef.current = true
          sendSystemMessage(
            dataChannelRef.current,
            'Time is running short. Finish the current topic, skip anything not essential, '
            + 'and move toward closing the interview.'
          )
        }

        if (!closingFiredRef.current && remaining <= closing) {
          closingFiredRef.current = true
          sendSystemMessage(
            dataChannelRef.current,
            'Time is almost up. Say a short, warm goodbye now: thank the candidate and tell '
            + 'them the employer will be in touch. Then end the interview.'
          )
          if (dataChannelRef.current?.readyState === 'open') {
            dataChannelRef.current.send(JSON.stringify({ type: 'response.create' }))
          }
        }

        if (remaining <= 1) {
          endInterview()
        }
      }, 1000)

      setPhase('active')
    } catch (err) {
      cleanup()
      setError(
        err?.name === 'NotAllowedError'
          ? 'Camera and microphone access is required for the interview.'
          : err?.response?.data?.message || err.message || 'Something went wrong starting the interview.'
      )
      setErrorCode(err?.response?.data?.code ?? null)
      setPhase('error')
    }
  }, [startSession, endInterview, handleAiEndRequest, handleAiAudioStopped])

  const notifyEmployer = useCallback(async () => {
    if (!requestReset) return
    setResetRequestState('sending')
    try {
      const result = await requestReset()
      setResetRequestState(result?.already_requested ? 'already_sent' : 'sent')
    } catch {
      setResetRequestState('error')
    }
  }, [requestReset])

  // Shared between the consent screen (candidate already used up both
  // attempts before ever clicking Start — sessionStartCount >= 2) and the
  // error screen (they clicked Start and the backend rejected it, e.g. a
  // second tab racing them to the second restart).
  const notifyEmployerAction = (
    <div className="space-y-3">
      {resetRequestState === 'sent' && (
        <p className="text-sm text-green-700 flex items-center gap-1.5">
          <CheckCircle2 size={16} />
          Your recruiter has been notified. They'll resend your invite once
          it's reset.
        </p>
      )}
      {resetRequestState === 'already_sent' && (
        <p className="text-sm text-text-muted">
          Your recruiter was already notified. No need to send this again.
        </p>
      )}
      {resetRequestState === 'error' && (
        <p className="text-sm text-red-700">
          Couldn't send that request. Please try again.
        </p>
      )}
      {(resetRequestState === 'idle' || resetRequestState === 'error') && (
        <Button onClick={notifyEmployer} className="w-full">
          Notify your recruiter
        </Button>
      )}
      {resetRequestState === 'sending' && (
        <Button disabled className="w-full">
          Sending…
        </Button>
      )}
    </div>
  )

  const { warn: warnThreshold, closing: closingThreshold } = thresholdsRef.current
  const timerUrgency = secondsLeft === null
    ? 'normal'
    : secondsLeft <= closingThreshold
      ? 'closing'
      : secondsLeft <= warnThreshold
        ? 'warn'
        : 'normal'

  return (
    <main className="min-h-screen bg-background flex flex-col items-center justify-center px-4 py-10">
      <audio ref={remoteAudioRef} autoPlay className="hidden" />

      <div className="w-full max-w-xl">
        {backTo && (
          <Link
            to={backTo}
            className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text mb-6"
          >
            <ArrowLeft size={14} />
            {backLabel}
          </Link>
        )}

        {phase === 'consent' && sessionStartCount >= 2 && (
          <div className="rounded-xl border border-border bg-surface p-6 space-y-5">
            <div>
              <h1 className="text-xl font-bold text-text">Video interview</h1>
              {subtitle && <p className="text-sm text-text-muted mt-1">{subtitle}</p>}
            </div>

            <div className="flex items-start gap-2.5 rounded-lg border border-red-300 bg-red-50 p-3.5">
              <AlertCircle size={18} className="text-red-600 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-800 leading-relaxed">
                <strong>You've already used both attempts on this interview.</strong>{' '}
                Starting won't work anymore. You'll need your recruiter to reset it
                before you can try again.
              </p>
            </div>

            {requestReset ? (
              notifyEmployerAction
            ) : (
              <p className="text-sm text-text-muted">
                Please contact your recruiter to have this interview reset.
              </p>
            )}
          </div>
        )}

        {phase === 'consent' && sessionStartCount < 2 && (
          <div className="rounded-xl border border-border bg-surface p-6 space-y-5">
            <div>
              <h1 className="text-xl font-bold text-text">Video interview</h1>
              {subtitle && <p className="text-sm text-text-muted mt-1">{subtitle}</p>}
            </div>

            {sessionStartCount >= 1 && (
              <div className="flex items-start gap-2.5 rounded-lg border border-amber-300 bg-amber-50 p-3.5">
                <AlertCircle size={18} className="text-amber-600 mt-0.5 flex-shrink-0" />
                <p className="text-sm text-amber-800 leading-relaxed">
                  <strong>You've already started this interview once.</strong> This is
                  your last attempt. Leaving or reloading again will lock you out of
                  completing it. Make sure your camera, microphone, and connection are
                  ready before you continue.
                </p>
              </div>
            )}

            <div>
              <p className="text-sm text-text-muted leading-relaxed mb-4">
                Please read these rules. You need to accept them before you can start.
              </p>
              <InterviewRules />
            </div>

            <p className="text-xs text-text-muted">
              Keep your answers focused. The interviewer will guide the conversation to cover
              every topic in the time available.
            </p>

            <label
              htmlFor="accept-interview-rules"
              className="flex items-start gap-2.5 rounded-lg border border-border bg-background p-3.5 cursor-pointer"
            >
              <input
                id="accept-interview-rules"
                type="checkbox"
                className="mt-0.5 h-4 w-4 flex-shrink-0"
                checked={accepted}
                onChange={(event) => setAccepted(event.target.checked)}
              />
              <span className="text-sm text-text">
                I have read these rules and I accept them.
              </span>
            </label>
            <Button onClick={startInterview} disabled={!accepted} className="w-full">
              Start the interview
            </Button>
          </div>
        )}

        {phase === 'connecting' && (
          <div className="rounded-xl border border-border bg-surface p-10 text-center space-y-3">
            <div className="w-8 h-8 border-2 border-brand-blue border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-sm text-text-muted">Connecting you with the interviewer…</p>
          </div>
        )}

        {(phase === 'active' || phase === 'ending') && (
          <div className="space-y-4">
            <div className="relative rounded-xl overflow-hidden bg-black aspect-video">
              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                className="w-full h-full object-cover"
              />
              <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-black/60 text-white text-xs font-medium px-2.5 py-1 rounded-full">
                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                {phase === 'ending' ? 'Ending…' : 'Recording'}
              </div>
              {secondsLeft !== null && (
                <div
                  className={
                    'absolute top-3 right-3 text-white text-xs font-medium px-2.5 py-1 rounded-full transition-colors '
                    + (timerUrgency === 'closing'
                      ? 'bg-red-600 animate-pulse'
                      : timerUrgency === 'warn'
                        ? 'bg-amber-600'
                        : 'bg-black/60')
                  }
                >
                  {formatTime(secondsLeft)}
                </div>
              )}
            </div>
            {timerUrgency === 'closing' && (
              <p className="text-xs text-red-600 text-center">
                Wrapping up. The interview will end automatically.
              </p>
            )}
            <Button
              variant="destructive"
              className="w-full"
              onClick={endInterview}
              disabled={phase === 'ending'}
            >
              {phase === 'ending' ? 'Ending interview…' : 'End interview'}
            </Button>
          </div>
        )}

        {phase === 'uploading' && (
          <div className="rounded-xl border border-border bg-surface p-8 text-center space-y-5">
            <div>
              <p className="font-semibold text-text">Your interview is finished.</p>
              <p className="text-sm text-text-muted mt-1">
                {uploadStep === 'confirming'
                  ? 'Almost done. Confirming your submission…'
                  : 'Now sending your recording to the employer.'}
              </p>
            </div>

            <div className="space-y-2">
              <p className="text-sm font-semibold text-text">{uploadProgress}%</p>
              <div
                className="h-3 w-full rounded-full bg-gray-200 overflow-hidden"
                role="progressbar"
                aria-label="Recording upload progress"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={uploadProgress}
              >
                <div
                  className="h-full bg-brand-blue transition-all"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>

            {uploadNote && (
              <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-2.5">
                {uploadNote}
              </p>
            )}

            <div className="flex items-start gap-2.5 rounded-lg border border-red-300 bg-red-50 p-3.5 text-left">
              <AlertCircle size={18} className="text-red-600 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-800 leading-relaxed">
                <strong>Do not close, reload or leave this page</strong> until you see{' '}
                &ldquo;Interview submitted&rdquo;. If you leave now, your recording will be lost.
                On a slow connection this can take a few minutes.
              </p>
            </div>
          </div>
        )}

        {phase === 'upload_error' && (
          <div className="rounded-xl border border-amber-300 bg-amber-50 p-6 text-center space-y-4">
            <AlertCircle size={32} className="text-amber-600 mx-auto" />
            <div className="space-y-1">
              <p className="text-sm font-semibold text-amber-900">
                Your interview is finished, but the recording hasn&apos;t uploaded yet.
              </p>
              <p className="text-sm text-amber-800">{error}</p>
            </div>
            <p className="text-xs text-amber-800">
              Your recording is safe on this device. Check your internet connection, then try
              again. Please don&apos;t close or reload this page, or the recording will be lost.
            </p>
            <Button onClick={submitRecording} className="w-full">
              Retry upload
            </Button>
          </div>
        )}

        {phase === 'done' && (
          <div className="rounded-xl border border-border bg-surface p-10 text-center space-y-4">
            <CheckCircle2 size={40} className="text-green-600 mx-auto" />
            <div>
              <p className="font-semibold text-text">Interview submitted</p>
              <p className="text-sm text-text-muted mt-1">
                The employer will review your recording along with your application.
                You can now safely close this page.
              </p>
            </div>
            {doneAction && (
              <Button onClick={doneAction.onClick} className="w-full">
                {doneAction.label}
              </Button>
            )}
          </div>
        )}

        {phase === 'error' && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center space-y-4">
            <AlertCircle size={32} className="text-red-600 mx-auto" />
            <p className="text-sm text-red-700">{error}</p>

            {errorCode === 'INTERVIEW_RESTART_LOCKED' && requestReset ? (
              notifyEmployerAction
            ) : (
              <Button onClick={() => { endingRef.current = false; setPhase('consent') }} variant="outline">
                Try again
              </Button>
            )}
          </div>
        )}
      </div>
    </main>
  )
}
