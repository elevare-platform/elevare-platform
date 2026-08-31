import { useState, useRef, useCallback, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Mic, Video, AlertCircle, ArrowLeft, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

const REALTIME_URL = 'https://api.openai.com/v1/realtime/calls'

// ─── Helpers ────────────────────────────────────────────────────────────────

function pickRecorderMimeType() {
  const candidates = [
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm',
  ]
  return candidates.find((type) => MediaRecorder.isTypeSupported?.(type)) ?? 'video/webm'
}

function formatTime(totalSeconds) {
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
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
  // 'consent' | 'connecting' | 'active' | 'ending' | 'uploading' | 'done' | 'error'
  const [phase, setPhase] = useState('consent')
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

  useEffect(() => () => cleanup(), [])

  useEffect(() => {
    if (phase === 'active' && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current
    }
  }, [phase])

  function cleanup() {
    if (timerRef.current) clearInterval(timerRef.current)
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

  const endInterview = useCallback(async () => {
    if (endingRef.current) return
    endingRef.current = true
    if (timerRef.current) clearInterval(timerRef.current)
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

    setPhase('uploading')
    try {
      const blob = new Blob(chunksRef.current, { type: pickRecorderMimeType() })

      const uploadInfo = await requestUploadUrl()

      const putResponse = await fetch(uploadInfo.upload_url, {
        method: 'PUT',
        headers: { 'Content-Type': 'video/webm' },
        body: blob,
      })
      if (!putResponse.ok) {
        throw new Error('Upload failed. Please try again.')
      }

      await completeUpload({ transcript: formatTranscript(), realtimeUsage: usageRef.current })
      setPhase('done')
    } catch (err) {
      setError(err?.response?.data?.message || err.message || 'Failed to upload your recording.')
      setPhase('error')
    }
  }, [requestUploadUrl, completeUpload])

  const startInterview = useCallback(async () => {
    setError(null)
    setErrorCode(null)
    setResetRequestState('idle')
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
      thresholdsRef.current = {
        totalSeconds,
        warn: clamp(totalSeconds * 0.2, 15, 60),
        closing: clamp(totalSeconds * 0.05, 5, 10),
        checkinInterval: clamp(totalSeconds * 0.25, 60, 180),
      }
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
            + 'Keep the conversation moving so you can cover the remaining topics in the brief.'
          )
        }

        if (!warnFiredRef.current && remaining <= warn) {
          warnFiredRef.current = true
          sendSystemMessage(
            dataChannelRef.current,
            'Only a few minutes remain in this interview. Begin wrapping up your current line of questioning.'
          )
        }

        if (!closingFiredRef.current && remaining <= closing) {
          closingFiredRef.current = true
          sendSystemMessage(
            dataChannelRef.current,
            'Time is almost up. Give a brief one-sentence thank-you and conclude the interview now.'
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
  }, [startSession, endInterview])

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
              <h1 className="text-xl font-bold text-text">AI video interview</h1>
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
              <h1 className="text-xl font-bold text-text">AI video interview</h1>
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

            <p className="text-sm text-text-muted leading-relaxed">
              You'll be speaking with an <strong>AI interviewer</strong>, not a human.
              It will ask you questions and follow up based on what you say, the same
              way a real interview would.
            </p>
            <ul className="text-sm text-text-muted space-y-2">
              <li className="flex items-start gap-2">
                <Video size={16} className="mt-0.5 flex-shrink-0" />
                Your camera will record the full session, including the AI
                interviewer's spoken questions. The employer reviews this
                recording.
              </li>
              <li className="flex items-start gap-2">
                <Mic size={16} className="mt-0.5 flex-shrink-0" />
                Your microphone stays on for the length of the interview so the AI can
                hear and respond to you live.
              </li>
              <li className="flex items-start gap-2">
                <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
                This is a <strong>single continuous session</strong>. Leaving or
                reloading the page ends your connection to the AI interviewer. You
                get one restart if something goes wrong (a dropped connection, a
                closed tab), but a second restart will lock you out of completing the
                interview.
              </li>
            </ul>
            <p className="text-xs text-text-muted">
              Keep your answers focused. The AI will guide the conversation to cover
              every topic in the time available.
            </p>
            <p className="text-xs text-text-muted">
              The session is processed by AI and reviewed by the employer. It will
              automatically end after the maximum interview length.
            </p>
            <Button onClick={startInterview} className="w-full">
              I understand, start the interview
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
          <div className="rounded-xl border border-border bg-surface p-10 text-center space-y-3">
            <div className="w-8 h-8 border-2 border-brand-blue border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-sm text-text-muted">Uploading your recording…</p>
          </div>
        )}

        {phase === 'done' && (
          <div className="rounded-xl border border-border bg-surface p-10 text-center space-y-4">
            <CheckCircle2 size={40} className="text-green-600 mx-auto" />
            <div>
              <p className="font-semibold text-text">Interview submitted</p>
              <p className="text-sm text-text-muted mt-1">
                The employer will review your recording along with your application.
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
