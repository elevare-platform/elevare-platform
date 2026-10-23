import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertCircle, ArrowLeft, CheckCircle2, Loader2, Maximize } from 'lucide-react'
import { Button } from '@/components/ui/button'
import InterviewRules from '@/components/candidate/InterviewRules'
import { STRICT_RULES_VERSION, STRICT_RULE_GROUPS } from '@/lib/interviewRules'
import { MAX_ATTEMPTS, uploadRecording, withRetry } from '@/lib/interviewUpload'
import {
  checkDevice,
  formatClock,
  pickAnswerMimeType,
  pickInterviewMimeType,
  shouldBlockKey,
  turnLabel,
} from '@/lib/strictInterview'

// The phases that are the interview itself: the screen is full screen and locked down.
const LIVE_PHASES = ['question', 'sending', 'send_error']

// The server's own words when it sent any (its messages name the problem).
function serverMessage(err, fallback) {
  const message = err?.response?.data?.message
  return typeof message === 'string' && message ? message : fallback
}

function stopTracks(stream) {
  stream?.getTracks().forEach((track) => track.stop())
}

// Stops a recorder and resolves with everything it recorded.
function stopRecorder(recorder, chunks, type) {
  return new Promise((resolve) => {
    if (!recorder || recorder.state === 'inactive') {
      resolve(new Blob(chunks, { type }))
      return
    }
    recorder.onstop = () => resolve(new Blob(chunks, { type: recorder.mimeType || type }))
    recorder.stop()
  })
}

/**
 * StrictInterviewFlow - the strict AI interview: the questions are shown as text at the top of
 * a locked full screen and the candidate answers each one by speaking to the camera.
 *
 * Shared by the logged-in candidate route and the emailed-link route, like InterviewFlow: each
 * supplies the four async functions below. The SERVER owns the clock and the position: every
 * call returns what is on screen now and how many seconds are left, so a reload resumes the
 * same question and nothing here can buy more time.
 *
 *   startInterview({ accepted, rulesVersion }) -> state   start, or resume after a reload
 *   sendAnswer(turnId, audioBlob)              -> state   the next question, a follow-up, or finished
 *   requestUploadUrl() / completeUpload()                 as for the live interview
 *
 * Built so far: the device check, the rules, full screen, the questions with their timers, the
 * spoken answers and follow-ups. NOT built yet (phase 3): noticing and recording that the
 * candidate left, warnings, ending the interview for it, and "I need to stop".
 */
export default function StrictInterviewFlow({
  startInterview,
  sendAnswer,
  requestUploadUrl,
  completeUpload,
  backTo,
  backLabel = 'Back',
  subtitle = null,
  doneAction = null,
  resuming = false,
  completed = false,
  maxMinutes = 20,
}) {
  // 'gate' | 'starting' | 'question' | 'sending' | 'send_error' | 'ending' | 'uploading'
  // | 'upload_error' | 'done' | 'error'
  const [phase, setPhase] = useState(completed ? 'done' : 'gate')
  const [accepted, setAccepted] = useState(false)
  const [device] = useState(() => checkDevice())
  const [state, setState] = useState(null)
  const [secondsLeft, setSecondsLeft] = useState(0)
  const [totalLeft, setTotalLeft] = useState(0)
  const [fullscreenLost, setFullscreenLost] = useState(false)
  const [error, setError] = useState(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadStep, setUploadStep] = useState('sending')
  const [uploadNote, setUploadNote] = useState(null)

  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const interviewRecorderRef = useRef(null)
  const interviewChunksRef = useRef([])
  const answerRecorderRef = useRef(null)
  const answerChunksRef = useRef([])
  const answerBlobRef = useRef(null)
  const turnIdRef = useRef(null)
  const turnDeadlineRef = useRef(0)
  const totalDeadlineRef = useRef(0)
  const timerRef = useRef(null)
  const submittingRef = useRef(false)
  const finishingRef = useRef(false)
  const recordingBlobRef = useRef(null)
  const fileUploadedRef = useRef(false)

  const isLive = LIVE_PHASES.includes(phase)
  const guardAgainstLeaving = isLive || ['ending', 'uploading', 'upload_error'].includes(phase)

  // A reload or closed tab loses the recording kept in memory. Ask the browser to confirm first.
  useEffect(() => {
    if (!guardAgainstLeaving) return undefined
    const warn = (event) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [guardAgainstLeaving])

  // While the interview runs: no right-click, copy, cut, paste, selecting or dragging, and the
  // shortcuts that open, close or switch tabs and windows are blocked. This is a deterrent, not
  // a guarantee: a web page cannot stop everything an operating system does.
  useEffect(() => {
    if (!isLive) return undefined
    const stop = (event) => event.preventDefault()
    const onKey = (event) => {
      if (shouldBlockKey(event)) {
        event.preventDefault()
        event.stopPropagation()
      }
    }
    const events = ['contextmenu', 'copy', 'cut', 'paste', 'selectstart', 'dragstart']
    events.forEach((name) => document.addEventListener(name, stop))
    document.addEventListener('keydown', onKey, true)
    return () => {
      events.forEach((name) => document.removeEventListener(name, stop))
      document.removeEventListener('keydown', onKey, true)
    }
  }, [isLive])

  // Leaving full screen puts a block in front of the questions until the candidate returns.
  // (Recording that it happened is phase 3.)
  useEffect(() => {
    if (!isLive) return undefined
    const onChange = () => setFullscreenLost(!document.fullscreenElement)
    document.addEventListener('fullscreenchange', onChange)
    onChange()
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [isLive])

  // The self-view shows whenever the interview is on screen.
  useEffect(() => {
    if (isLive && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current
    }
  }, [isLive, phase])

  const releaseEverything = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current)
    for (const recorder of [answerRecorderRef.current, interviewRecorderRef.current]) {
      if (recorder && recorder.state !== 'inactive') {
        try { recorder.stop() } catch { /* already stopped */ }
      }
    }
    stopTracks(streamRef.current)
    streamRef.current = null
    try { navigator.keyboard?.unlock?.() } catch { /* not supported */ }
    if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {})
  }, [])

  useEffect(() => () => releaseEverything(), [releaseEverything])

  // ── Recording ────────────────────────────────────────────────────────────

  const startInterviewRecording = useCallback((stream) => {
    const mimeType = pickInterviewMimeType()
    interviewChunksRef.current = []
    const recorder = new MediaRecorder(stream, { mimeType })
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) interviewChunksRef.current.push(event.data)
    }
    recorder.start(1000)
    interviewRecorderRef.current = recorder
  }, [])

  const startAnswerRecording = useCallback(() => {
    const stream = streamRef.current
    const mimeType = pickAnswerMimeType()
    answerChunksRef.current = []
    answerBlobRef.current = null
    if (!stream || !mimeType) return
    const recorder = new MediaRecorder(new MediaStream(stream.getAudioTracks()), { mimeType })
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) answerChunksRef.current.push(event.data)
    }
    recorder.start()
    answerRecorderRef.current = recorder
  }, [])

  // ── Sending the whole recording, once the questions are done ─────────────

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
      setUploadNote(null)
      setUploadProgress(100)
      setUploadStep('confirming')
      await withRetry(() => completeUpload())
      recordingBlobRef.current = null
      setPhase('done')
    } catch (err) {
      if (err?.response?.data?.code === 'RECORDING_NOT_RECEIVED') fileUploadedRef.current = false
      setError(serverMessage(err, 'We could not upload your recording. Your connection may have dropped.'))
      setPhase('upload_error')
    }
  }, [requestUploadUrl, completeUpload])

  const finishInterview = useCallback(async () => {
    if (finishingRef.current) return
    finishingRef.current = true
    if (timerRef.current) clearInterval(timerRef.current)
    setPhase('ending')
    if (answerRecorderRef.current && answerRecorderRef.current.state !== 'inactive') {
      try { answerRecorderRef.current.stop() } catch { /* already stopped */ }
    }
    const recorder = interviewRecorderRef.current
    recordingBlobRef.current = await stopRecorder(recorder, interviewChunksRef.current, 'video/webm')
    fileUploadedRef.current = false
    stopTracks(streamRef.current)
    streamRef.current = null
    try { navigator.keyboard?.unlock?.() } catch { /* not supported */ }
    if (document.fullscreenElement) await document.exitFullscreen?.().catch(() => {})
    await submitRecording()
  }, [submitRecording])

  // ── The questions ────────────────────────────────────────────────────────

  const submitAnswerRef = useRef(null)

  const beginTurn = useCallback((next) => {
    setState(next)
    totalDeadlineRef.current = Date.now() + next.seconds_left_total * 1000
    if (next.finished || !next.turn) {
      finishInterview()
      return
    }
    turnIdRef.current = next.turn.id
    turnDeadlineRef.current = Date.now() + next.turn.seconds_left * 1000
    setSecondsLeft(next.turn.seconds_left)
    setTotalLeft(next.seconds_left_total)
    submittingRef.current = false
    setPhase('question')
    startAnswerRecording()
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      const remaining = Math.max(0, Math.ceil((turnDeadlineRef.current - Date.now()) / 1000))
      setSecondsLeft(remaining)
      setTotalLeft(Math.max(0, Math.ceil((totalDeadlineRef.current - Date.now()) / 1000)))
      if (remaining <= 0) submitAnswerRef.current?.()
    }, 250)
  }, [finishInterview, startAnswerRecording])

  // Sends the recorded answer. Safe to call again after a failure: the same recording is sent,
  // and the server ignores an answer it already has.
  const deliverAnswer = useCallback(async () => {
    setError(null)
    setPhase('sending')
    try {
      const next = await withRetry(() => sendAnswer(turnIdRef.current, answerBlobRef.current))
      beginTurn(next)
    } catch (err) {
      setError(serverMessage(err, 'We could not send your answer. Check your connection and try again.'))
      setPhase('send_error')
    }
  }, [sendAnswer, beginTurn])

  const submitAnswer = useCallback(async () => {
    if (submittingRef.current) return
    submittingRef.current = true
    if (timerRef.current) clearInterval(timerRef.current)
    setPhase('sending')
    answerBlobRef.current = await stopRecorder(
      answerRecorderRef.current,
      answerChunksRef.current,
      'audio/webm'
    )
    await deliverAnswer()
  }, [deliverAnswer])

  useEffect(() => {
    submitAnswerRef.current = submitAnswer
  }, [submitAnswer])

  // ── Starting ─────────────────────────────────────────────────────────────

  const requestFullscreen = async () => {
    await document.documentElement.requestFullscreen({ navigationUI: 'hide' })
    // Captures Esc and the shortcuts for as long as full screen lasts (Chrome and Edge only).
    try { await navigator.keyboard?.lock?.() } catch { /* not supported or refused */ }
  }

  const begin = async () => {
    setError(null)
    finishingRef.current = false
    setPhase('starting')
    try {
      // Full screen first: the browser only allows it straight after the candidate's click.
      try {
        await requestFullscreen()
      } catch (err) {
        throw new Error('The interview needs full screen. Please allow it and try again.', { cause: err })
      }
      let stream
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
          video: true,
        })
      } catch (err) {
        throw new Error(
          err?.name === 'NotAllowedError'
            ? 'Camera and microphone access is required for the interview.'
            : 'We could not use your camera and microphone. Check they are connected and not in use by another app.',
          { cause: err }
        )
      }
      streamRef.current = stream
      const next = await startInterview({ accepted: true, rulesVersion: STRICT_RULES_VERSION })
      startInterviewRecording(stream)
      beginTurn(next)
    } catch (err) {
      releaseEverything()
      setError(serverMessage(err, err?.message || 'Something went wrong starting the interview.'))
      setPhase('error')
    }
  }

  const returnToFullScreen = async () => {
    try { await requestFullscreen() } catch { /* the block stays until it works */ }
  }

  // ── Screens ──────────────────────────────────────────────────────────────

  const turn = state?.turn ?? null
  const canStart = device.ok && (resuming || accepted)

  if (isLive) {
    const busy = phase !== 'question'
    return (
      <div className="fixed inset-0 z-50 flex flex-col bg-white select-none" data-testid="strict-interview">
        <header className="border-b border-border bg-surface px-6 py-5">
          <div className="mx-auto flex max-w-3xl items-start justify-between gap-6">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-brand-blue">
                {turnLabel(turn, state?.total_questions)}
              </p>
              <p className="mt-2 text-xl font-semibold leading-snug text-text" data-testid="question-text">
                {turn?.text}
              </p>
            </div>
            <div className="flex-shrink-0 text-right">
              <p className="text-xs text-text-muted">Time for this question</p>
              <p
                className={'text-2xl font-bold tabular-nums ' + (secondsLeft <= 15 ? 'text-red-600' : 'text-text')}
                aria-label="Time left for this question"
              >
                {formatClock(secondsLeft)}
              </p>
            </div>
          </div>
        </header>

        <main className="flex flex-1 flex-col items-center justify-center gap-4 px-6">
          <div className="relative w-full max-w-xl overflow-hidden rounded-xl bg-black aspect-video">
            <video ref={videoRef} autoPlay muted playsInline className="h-full w-full -scale-x-100 object-cover" />
            <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 text-xs font-medium text-white">
              <span className="h-2 w-2 animate-pulse rounded-full bg-red-500" />
              Recording
            </div>
          </div>
          <p className="text-sm text-text-muted">Look at the camera and speak your answer.</p>
          {phase === 'send_error' && (
            <div role="alert" className="w-full max-w-xl space-y-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-center">
              <p className="text-sm text-amber-900">{error}</p>
              <Button onClick={deliverAnswer} className="w-full">Try again</Button>
            </div>
          )}
        </main>

        <footer className="border-t border-border bg-surface px-6 py-4">
          <div className="mx-auto flex max-w-3xl items-center justify-between gap-4">
            <p className="text-xs text-text-muted">
              Whole interview: {formatClock(totalLeft)} left of {maxMinutes} minutes
            </p>
            <Button onClick={submitAnswer} disabled={busy}>
              {phase === 'sending' ? (
                <span className="inline-flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Sending your answer…</span>
              ) : (
                'Next'
              )}
            </Button>
          </div>
        </footer>

        {fullscreenLost && (
          <div
            role="alertdialog"
            aria-label="Return to full screen"
            className="absolute inset-0 z-10 flex items-center justify-center bg-white px-6"
          >
            <div className="max-w-sm space-y-4 text-center">
              <Maximize size={32} className="mx-auto text-brand-blue" />
              <p className="font-semibold text-text">The interview needs full screen</p>
              <p className="text-sm text-text-muted">
                Return to full screen to see the question. The time keeps running.
              </p>
              <Button onClick={returnToFullScreen} className="w-full">Return to full screen</Button>
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-background flex flex-col items-center justify-center px-4 py-10">
      <div className="w-full max-w-xl">
        {backTo && phase !== 'ending' && phase !== 'uploading' && (
          <Link
            to={backTo}
            className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text mb-6"
          >
            <ArrowLeft size={14} />
            {backLabel}
          </Link>
        )}

        {phase === 'gate' && (
          <div className="rounded-xl border border-border bg-surface p-6 space-y-5">
            <div>
              <h1 className="text-xl font-bold text-text">AI video interview</h1>
              {subtitle && <p className="text-sm text-text-muted mt-1">{subtitle}</p>}
              <p className="text-sm text-text-muted mt-2">
                You will see each question on screen and answer it out loud, to the camera.
                It lasts at most {maxMinutes} minutes.
              </p>
            </div>

            {!device.ok && (
              <div role="alert" className="space-y-2 rounded-lg border border-red-300 bg-red-50 p-3.5">
                {device.problems.map((problem) => (
                  <p key={problem.id} className="flex items-start gap-2.5 text-sm text-red-800 leading-relaxed">
                    <AlertCircle size={18} className="mt-0.5 flex-shrink-0 text-red-600" />
                    {problem.message}
                  </p>
                ))}
              </div>
            )}

            {resuming ? (
              <div className="flex items-start gap-2.5 rounded-lg border border-amber-300 bg-amber-50 p-3.5">
                <AlertCircle size={18} className="text-amber-600 mt-0.5 flex-shrink-0" />
                <p className="text-sm text-amber-800 leading-relaxed">
                  <strong>You started this interview earlier.</strong> Continue to return to the
                  question you were on. The time that passed has not been paused.
                </p>
              </div>
            ) : (
              <>
                <div>
                  <p className="text-sm text-text-muted leading-relaxed mb-4">
                    Please read these rules. You need to accept them before you can start.
                  </p>
                  <InterviewRules groups={STRICT_RULE_GROUPS} />
                </div>
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
                  <span className="text-sm text-text">I have read these rules and I accept them.</span>
                </label>
              </>
            )}

            <p className="text-xs text-text-muted">
              When you press the button the screen goes full screen and your browser asks to use
              your camera and microphone.
            </p>
            <Button onClick={begin} disabled={!canStart} className="w-full">
              {resuming ? 'Continue the interview' : 'Start the interview'}
            </Button>
          </div>
        )}

        {phase === 'starting' && (
          <div className="rounded-xl border border-border bg-surface p-10 text-center space-y-3">
            <div className="w-8 h-8 border-2 border-brand-blue border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-sm text-text-muted">Getting your interview ready…</p>
          </div>
        )}

        {phase === 'ending' && (
          <div className="rounded-xl border border-border bg-surface p-10 text-center space-y-3">
            <div className="w-8 h-8 border-2 border-brand-blue border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-sm text-text-muted">Your interview is finished. Wrapping up…</p>
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
                <div className="h-full bg-brand-blue transition-all" style={{ width: `${uploadProgress}%` }} />
              </div>
            </div>
            {uploadNote && (
              <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-2.5">{uploadNote}</p>
            )}
            <div className="flex items-start gap-2.5 rounded-lg border border-red-300 bg-red-50 p-3.5 text-left">
              <AlertCircle size={18} className="text-red-600 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-800 leading-relaxed">
                <strong>Do not close, reload or leave this page</strong> until you see
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
            <Button onClick={submitRecording} className="w-full">Retry upload</Button>
          </div>
        )}

        {phase === 'done' && (
          <div className="rounded-xl border border-border bg-surface p-10 text-center space-y-4">
            <CheckCircle2 size={40} className="text-green-600 mx-auto" />
            <div>
              <p className="font-semibold text-text">Interview submitted</p>
              <p className="text-sm text-text-muted mt-1">
                The employer will review your recording along with your application. You can now
                safely close this page.
              </p>
            </div>
            {doneAction && (
              <Button onClick={doneAction.onClick} className="w-full">{doneAction.label}</Button>
            )}
          </div>
        )}

        {phase === 'error' && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center space-y-4">
            <AlertCircle size={32} className="text-red-600 mx-auto" />
            <p className="text-sm text-red-700">{error}</p>
            <Button onClick={() => setPhase('gate')} variant="outline">Try again</Button>
          </div>
        )}
      </div>
    </main>
  )
}
