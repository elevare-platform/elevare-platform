import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertCircle, ArrowLeft, CheckCircle2, Loader2, Maximize } from 'lucide-react'
import { Button } from '@/components/ui/button'
import InterviewRules from '@/components/candidate/InterviewRules'
import { useLeaveWatch } from '@/hooks/useLeaveWatch'
import { STRICT_MONITORING, STRICT_RULES_VERSION, strictRuleGroups } from '@/lib/interviewRules'
import { MAX_ATTEMPTS, uploadRecording, withRetry } from '@/lib/interviewUpload'
import { openRecordingStore } from '@/lib/recordingStore'
import { salvagePreviousRecordings } from '@/lib/recordingSalvage'
import {
  ENDED_FOOTER,
  HEARTBEAT_MS,
  KEY_REPEAT_MS,
  KEY_WARNING,
  WARNING_SHOW_MS,
  endedMessage,
  AWAY_TITLE,
  awayTone,
  leaveNotice as leaveNoticeFor,
  reasonFromStatus,
  reportableKey,
} from '@/lib/strictConduct'
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

// A name for one recording, so a reload never mixes it with an earlier one.
function newSegmentId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`
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
 *   reportEvent({ type, cause?, key? })        -> state   a leave, a return, a key press, a heartbeat
 *   stopInterview()                            -> state   "I need to stop", after the confirmation
 *   requestUploadUrl() / completeUpload()                 as for the live interview
 *
 * Every reply is the server's state, and may say the interview has ENDED (too many leaves, too
 * long away, or stopped): the screen then stops recording, still sends the recording and the
 * answers (the employer reviews them and can reinstate it), and says so. The first three leaves
 * warn; what ends an interview, and how long a leave lasted, is decided by the server's clock.
 */
export default function StrictInterviewFlow({
  startInterview,
  sendAnswer,
  reportEvent,
  stopInterview,
  requestUploadUrl,
  completeUpload,
  requestPartUploadUrl,
  backTo,
  backLabel = 'Back',
  subtitle = null,
  doneAction = null,
  resuming = false,
  // The employer reinstated an interview that ended: the candidate carries on where they stopped.
  reinstated = false,
  completed = false,
  // The status of an interview that has already ended when the page opens (ENDED_CONDUCT or STOPPED).
  endedStatus = null,
  maxMinutes = 20,
  // What the AI may do after an answer, chosen by the employer for this job (NONE, STANDARD or
  // PROBES_ONLY): the rules shown before the start say which.
  followUpMode = 'STANDARD',
  // Where the recording is kept while it is made, so a reload does not lose it. Left out, the
  // browser's own storage is used; null (no storage) records in memory only, as before.
  recordingStore: providedStore,
}) {
  const [recordingStore] = useState(() => (providedStore !== undefined ? providedStore : openRecordingStore()))
  // 'gate' | 'starting' | 'question' | 'sending' | 'send_error' | 'ending' | 'uploading'
  // | 'upload_error' | 'done' | 'ended' | 'error'
  const [endedReason, setEndedReason] = useState(() => reasonFromStatus(endedStatus))
  const [phase, setPhase] = useState(
    endedStatus && reasonFromStatus(endedStatus) ? 'ended' : completed ? 'done' : 'gate'
  )
  // The warning on screen (about leaving, or about a key), and how the server counts so far.
  const [warning, setWarning] = useState(null)
  const [conduct, setConduct] = useState(null)
  // The camera and microphone check on the first screen: 'idle' | 'asking' | 'ready'.
  const [cameraState, setCameraState] = useState('idle')
  const [cameraError, setCameraError] = useState(null)
  // The box that dims the screen when the candidate comes back from leaving it: null, or what
  // to show. `text` is empty until the server has counted the leave.
  const [leaveNotice, setLeaveNotice] = useState(null)
  const [confirmStop, setConfirmStop] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [stopError, setStopError] = useState(null)
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
  const previewRef = useRef(null)
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
  const interviewIdRef = useRef(null)
  const segmentRef = useRef(null)
  const salvageRef = useRef(null)
  // Why the interview ended, once it has: read by the code that finishes and uploads.
  const endedReasonRef = useRef(reasonFromStatus(endedStatus))
  const warningTimerRef = useRef(null)
  const lastKeyRef = useRef({ name: null, at: 0 })
  const sendEventRef = useRef(null)

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
      // A key that tries to leave is told to the server (once, not for every repeat of a held
      // key) and warned about on screen. It never ends the interview.
      const name = reportableKey(event)
      if (name) {
        const last = lastKeyRef.current
        const now = Date.now()
        if (name !== last.name || now - last.at > KEY_REPEAT_MS) {
          lastKeyRef.current = { name, at: now }
          sendEventRef.current?.({ type: 'key', key: name })
        }
      }
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
  // (It is also one of the ways of leaving that the server counts: see useLeaveWatch below.)
  useEffect(() => {
    if (!isLive) return undefined
    const onChange = () => setFullscreenLost(!document.fullscreenElement)
    document.addEventListener('fullscreenchange', onChange)
    onChange()
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [isLive])

  // The self-view shows whenever the interview is on screen, and the preview on the first screen.
  useEffect(() => {
    if (isLive && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current
    }
  }, [isLive, phase])

  useEffect(() => {
    if (phase === 'gate' && cameraState === 'ready' && previewRef.current && streamRef.current) {
      previewRef.current.srcObject = streamRef.current
    }
  }, [phase, cameraState])

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

  useEffect(() => () => {
    releaseEverything()
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current)
  }, [releaseEverything])

  // ── Recording ────────────────────────────────────────────────────────────

  // Every chunk is also kept in the browser's storage under this recording's own id, so that a
  // reload, a crash or a closed tab leaves it there to be sent when the candidate comes back.
  const startInterviewRecording = useCallback((stream, interviewId) => {
    const mimeType = pickInterviewMimeType()
    interviewChunksRef.current = []
    const segment = newSegmentId()
    segmentRef.current = segment
    let index = 0
    const recorder = new MediaRecorder(stream, { mimeType })
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        interviewChunksRef.current.push(event.data)
        recordingStore?.addChunk(interviewId, segment, index++, event.data)
      }
    }
    recorder.start(1000)
    interviewRecorderRef.current = recorder
  }, [recordingStore])

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
      // The interview is over and the server has it all, so nothing needs keeping here.
      recordingStore?.deleteInterview(interviewIdRef.current)
      setPhase(endedReasonRef.current ? 'ended' : 'done')
    } catch (err) {
      if (err?.response?.data?.code === 'RECORDING_NOT_RECEIVED') fileUploadedRef.current = false
      setError(serverMessage(err, 'We could not upload your recording. Your connection may have dropped.'))
      setPhase('upload_error')
    }
  }, [requestUploadUrl, completeUpload, recordingStore])

  // The questions are done, or the interview ended early (`reason` is the server's: too many
  // leaves, too long away, or stopped). Either way the recording is sent and the interview
  // completed; an ended interview then shows the ended screen instead of "submitted".
  const finishInterview = useCallback(async (reason = null) => {
    if (finishingRef.current) return
    finishingRef.current = true
    if (reason) {
      endedReasonRef.current = reason
      setEndedReason(reason)
    }
    setConfirmStop(false)
    setWarning(null)
    setLeaveNotice(null)
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
    // Earlier recordings (before a reload) are being sent as parts. They must be on the server
    // before the interview is completed, since the server joins them with this one then.
    await salvageRef.current
    await submitRecording()
  }, [submitRecording])

  // ── The questions ────────────────────────────────────────────────────────

  const submitAnswerRef = useRef(null)

  const beginTurn = useCallback((next) => {
    setState(next)
    setConduct(next)
    totalDeadlineRef.current = Date.now() + next.seconds_left_total * 1000
    if (next.ended) {
      finishInterview(next.ended)
      return
    }
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

  // ── Leaving, warnings, stopping ──────────────────────────────────────────

  const showWarning = useCallback((text) => {
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current)
    setWarning(text)
    if (text) warningTimerRef.current = setTimeout(() => setWarning(null), WARNING_SHOW_MS)
  }, [])

  // Tells the server something happened (a leave, a return, a key, a heartbeat) and acts on its
  // reply: it may say the interview has ended. A failure is not shown: the screen carries on and
  // the next event or heartbeat tells the server. A return is retried, since the server keeps
  // counting a leave until it hears the candidate is back.
  const sendEvent = useCallback(async (body) => {
    if (!reportEvent || finishingRef.current) return
    if (body.type === 'key') showWarning(KEY_WARNING)
    try {
      const next = body.type === 'returned'
        ? await withRetry(() => reportEvent(body))
        : await reportEvent(body)
      setConduct(next)
      if (next.ended) {
        finishInterview(next.ended)
        return
      }
      if (body.type === 'returned') {
        // The server has counted the leave: say how many warnings are used and what is left.
        const notice = leaveNoticeFor(next)
        setLeaveNotice(notice ? { loading: false, ...notice } : null)
      }
    } catch {
      // The leave could not be counted just now. The candidate is still told to stay.
      if (body.type === 'returned') setLeaveNotice({ loading: false, failed: true })
    }
  }, [reportEvent, finishInterview, showWarning])

  useEffect(() => {
    sendEventRef.current = sendEvent
  }, [sendEvent])

  useLeaveWatch({
    active: isLive && Boolean(reportEvent),
    onLeft: (cause) => sendEvent({ type: 'left', cause }),
    // Coming back dims the screen and shows a box at once, so the candidate cannot miss that
    // leaving was noticed; the server's count fills it in a moment later.
    onReturned: () => {
      setLeaveNotice({ loading: true })
      sendEvent({ type: 'returned' })
    },
  })

  // While the candidate is on another tab the interview's tab says so in the tab list and the
  // taskbar, which is where they are looking.
  useEffect(() => {
    if (!isLive) return undefined
    const original = document.title
    const sync = () => {
      document.title = document.visibilityState === 'hidden' ? AWAY_TITLE : original
    }
    document.addEventListener('visibilitychange', sync)
    return () => {
      document.removeEventListener('visibilitychange', sync)
      document.title = original
    }
  }, [isLive])

  // The server times a reload from the last time the screen was heard from.
  useEffect(() => {
    if (!isLive || !reportEvent) return undefined
    const id = setInterval(() => sendEvent({ type: 'ping' }), HEARTBEAT_MS)
    return () => clearInterval(id)
  }, [isLive, reportEvent, sendEvent])

  const stopNow = async () => {
    if (!stopInterview) return
    setStopping(true)
    setStopError(null)
    try {
      const next = await stopInterview()
      setConduct(next)
      await finishInterview(next.ended ?? 'STOPPED')
    } catch (err) {
      setStopError(serverMessage(err, 'We could not stop the interview. Please try again.'))
    } finally {
      setStopping(false)
    }
  }

  // ── Starting ─────────────────────────────────────────────────────────────

  const requestFullscreen = async () => {
    await document.documentElement.requestFullscreen({ navigationUI: 'hide' })
    // Captures Esc and the shortcuts for as long as full screen lasts (Chrome and Edge only).
    try { await navigator.keyboard?.lock?.() } catch { /* not supported or refused */ }
  }

  // The browser asks for the camera and microphone in a pop-up that takes focus and can take the
  // page out of full screen. So that never happens during the interview (where it would count
  // as leaving the screen), it is asked here, on the first screen, before full screen. The
  // stream is kept and used for the interview, so starting asks for nothing more.
  const checkCamera = async () => {
    setCameraError(null)
    setCameraState('asking')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        video: true,
      })
      stopTracks(streamRef.current)
      streamRef.current = stream
      setCameraState('ready')
    } catch (err) {
      setCameraError(
        err?.name === 'NotAllowedError'
          ? 'Camera and microphone access is blocked. Allow it with the camera icon in the address bar, then press the button again.'
          : 'We could not use your camera and microphone. Check they are connected and not in use by another app, then press the button again.'
      )
      setCameraState('idle')
    }
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
      // The camera was checked on the first screen. If it has since gone (unplugged, taken by
      // another app) it is asked for again, which may bring up the pop-up.
      let stream = streamRef.current
      if (!stream || !stream.getTracks().every((track) => track.readyState === 'live')) {
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
      }
      const next = await startInterview({ accepted: true, rulesVersion: STRICT_RULES_VERSION })
      if (next.ended) {
        // It already ended (the employer has not reinstated it): nothing to record.
        releaseEverything()
        endedReasonRef.current = next.ended
        setEndedReason(next.ended)
        setPhase('ended')
        return
      }
      interviewIdRef.current = next.interview_id
      startInterviewRecording(stream, next.interview_id)
      // After a reload, what was recorded before it is still in storage. Send it in the
      // background (the first question is already running); finishing waits for it.
      salvageRef.current = salvagePreviousRecordings({
        store: recordingStore,
        interviewId: next.interview_id,
        currentSegment: segmentRef.current,
        requestPartUploadUrl,
      })
      beginTurn(next)
    } catch (err) {
      releaseEverything()
      setCameraState('idle')
      setError(serverMessage(err, err?.message || 'Something went wrong starting the interview.'))
      setPhase('error')
    }
  }

  const returnToFullScreen = async () => {
    try { await requestFullscreen() } catch { /* the block stays until it works */ }
  }

  // ── Screens ──────────────────────────────────────────────────────────────

  const turn = state?.turn ?? null
  const canStart = device.ok && cameraState === 'ready' && (resuming || accepted)

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

        {warning && (
          <div
            role="status"
            className="flex items-start justify-center gap-3 border-b border-amber-300 bg-amber-50 px-6 py-3 text-sm text-amber-900"
          >
            <AlertCircle size={16} className="mt-0.5 flex-shrink-0 text-amber-600" aria-hidden="true" />
            <p className="max-w-3xl">{warning}</p>
            <button
              type="button"
              onClick={() => showWarning(null)}
              aria-label="Dismiss the warning"
              className="flex-shrink-0 text-xs font-semibold text-amber-800 underline"
            >
              Dismiss
            </button>
          </div>
        )}

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
            <div className="space-y-1">
              <p className="text-xs text-text-muted">
                Whole interview: {formatClock(totalLeft)} left of {maxMinutes} minutes
              </p>
              {Number.isFinite(conduct?.max_away_seconds) && (
                // Always on screen, so the 60 second limit is never a surprise: it turns amber
                // at half and red near the limit.
                <p
                  className={'text-xs ' + awayTone(conduct)}
                  data-testid="away-time"
                >
                  Time away from this screen: {conduct.away_seconds} of {conduct.max_away_seconds} seconds
                  in total. At {conduct.max_away_seconds} the interview ends.
                </p>
              )}
              {conduct?.leaves > 0 && (
                <p className="text-xs text-amber-700" data-testid="warnings-used">
                  Warnings used: {Math.min(conduct.leaves, conduct.max_leaves - 1)} of {conduct.max_leaves - 1}.
                </p>
              )}
              {stopInterview && (
                <button
                  type="button"
                  onClick={() => { setStopError(null); setConfirmStop(true) }}
                  disabled={phase === 'sending'}
                  className="text-xs text-text-muted underline hover:text-text disabled:opacity-50"
                >
                  I need to stop
                </button>
              )}
            </div>
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

        {leaveNotice && (
          // The screen dims and a box says the leave was noticed. The candidate confirms it before
          // going on. The question timer keeps running behind it.
          <div
            role="alertdialog"
            aria-modal="true"
            aria-label="You left the interview screen"
            className="absolute inset-0 z-30 flex items-center justify-center bg-black/60 px-6"
          >
            <div className="w-full max-w-md space-y-4 rounded-xl bg-white p-6 text-center shadow-xl">
              <AlertCircle size={36} className="mx-auto text-amber-600" aria-hidden="true" />
              <p className="text-lg font-semibold text-text">You left the interview screen</p>
              {leaveNotice.loading && (
                <p className="text-sm text-text-muted">Checking how many warnings you have used…</p>
              )}
              {!leaveNotice.loading && leaveNotice.failed && (
                <p className="text-sm text-text-muted">
                  Please stay on this screen. Leaving it is noted and can end the interview.
                </p>
              )}
              {!leaveNotice.loading && !leaveNotice.failed && (
                <div className="space-y-2">
                  <p
                    className={'text-base font-bold ' + (leaveNotice.last ? 'text-red-600' : 'text-amber-700')}
                    data-testid="leave-warning-count"
                  >
                    Warning {leaveNotice.used} of {leaveNotice.allowed}
                  </p>
                  <div>
                    <p className="text-sm font-semibold text-text" data-testid="leave-away-used">
                      Time away used: {leaveNotice.away.used} of {leaveNotice.away.max} seconds
                    </p>
                    <div
                      role="progressbar"
                      aria-label="Time away used"
                      aria-valuemin={0}
                      aria-valuemax={leaveNotice.away.max}
                      aria-valuenow={leaveNotice.away.used}
                      className="mt-1 h-2 w-full overflow-hidden rounded-full bg-gray-200"
                    >
                      <div
                        className={'h-full ' + (leaveNotice.away.used >= leaveNotice.away.max * 0.8 ? 'bg-red-600' : 'bg-amber-500')}
                        style={{ width: `${Math.min(100, (leaveNotice.away.used / leaveNotice.away.max) * 100)}%` }}
                      />
                    </div>
                  </div>
                  {leaveNotice.lines.map((line) => (
                    <p key={line} className="text-sm text-text-muted">{line}</p>
                  ))}
                </div>
              )}
              <Button onClick={() => setLeaveNotice(null)} disabled={leaveNotice.loading} className="w-full">
                I understand, go back to the interview
              </Button>
            </div>
          </div>
        )}

        {confirmStop && (
          // Our own box, not window.confirm: the browser's would take the page out of full screen.
          <div
            role="alertdialog"
            aria-label="Stop the interview"
            className="absolute inset-0 z-20 flex items-center justify-center bg-black/40 px-6"
          >
            <div className="w-full max-w-sm space-y-4 rounded-xl bg-white p-6 text-center">
              <p className="font-semibold text-text">Stop the interview?</p>
              <p className="text-sm text-text-muted">
                The interview ends now. Your answers and your recording so far are sent to the
                employer, who is told you stopped and can let you carry on later.
              </p>
              {stopError && <p role="alert" className="text-sm text-red-700">{stopError}</p>}
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => setConfirmStop(false)}
                  disabled={stopping}
                >
                  Keep going
                </Button>
                <Button variant="destructive" className="flex-1" onClick={stopNow} disabled={stopping}>
                  {stopping ? 'Stopping…' : 'Stop the interview'}
                </Button>
              </div>
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
              <h1 className="text-xl font-bold text-text">Video interview</h1>
              {subtitle && <p className="text-sm text-text-muted mt-1">{subtitle}</p>}
              <p className="text-sm text-text-muted mt-2">
                You will see each question on screen and answer it out loud, to the camera.
                It lasts at most {maxMinutes} minutes.
              </p>
            </div>

            {/* What the assessment looks for, in three lines (the scorecard's opening prompt). */}
            <div className="rounded-lg border border-brand-blue/30 bg-brand-blue/5 p-3.5" data-testid="how-to-answer">
              <p className="text-sm font-semibold text-text">How to answer</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-text-muted">
                <li>Use specific examples. Say what you did yourself, as distinct from your team, and the result, with numbers if you have them.</li>
                <li>If a question asks what you would do, say what you are assuming and why.</li>
                <li>Every candidate for this role gets the same questions and is rated the same way.</li>
              </ul>
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
                {reinstated ? (
                  <p className="text-sm text-amber-800 leading-relaxed">
                    <strong>The employer has let you carry on with this interview.</strong> Continue
                    to return to the question you were on, with the time you had left. You start
                    again with all your warnings, and the answers you gave are kept.
                  </p>
                ) : (
                  <p className="text-sm text-amber-800 leading-relaxed">
                    <strong>You started this interview earlier.</strong> Continue to return to the
                    question you were on. The time that passed has not been paused, and coming back
                    counts as leaving the screen once.
                  </p>
                )}
              </div>
            ) : (
              <>
                <div>
                  <p className="text-sm text-text-muted leading-relaxed mb-4">
                    Please read these rules. You need to accept them before you can start.
                  </p>
                  <InterviewRules groups={strictRuleGroups(followUpMode)} monitoring={STRICT_MONITORING} />
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

            {/* The camera and microphone are allowed HERE, before full screen: the browser's
                permission pop-up would otherwise take the screen out of full screen. */}
            <div className="space-y-3 rounded-lg border border-border bg-background p-3.5">
              <p className="text-sm font-medium text-text">
                {resuming ? 'Check your camera and microphone' : 'Step 1: check your camera and microphone'}
              </p>
              {cameraState === 'ready' ? (
                <div className="space-y-2">
                  <video
                    ref={previewRef}
                    autoPlay
                    muted
                    playsInline
                    className="aspect-video w-full max-w-xs -scale-x-100 rounded-lg bg-black object-cover"
                  />
                  <p className="flex items-center gap-1.5 text-sm text-green-700">
                    <CheckCircle2 size={16} aria-hidden="true" /> Your camera and microphone are working.
                  </p>
                </div>
              ) : (
                <>
                  <p className="text-xs text-text-muted">
                    Your browser will ask to use your camera and microphone. Press Allow. This is done
                    now so that nothing pops up once the interview has started.
                  </p>
                  <Button variant="outline" onClick={checkCamera} disabled={!device.ok || cameraState === 'asking'}>
                    {cameraState === 'asking' ? 'Waiting for your browser…' : 'Check my camera and microphone'}
                  </Button>
                  {cameraError && <p role="alert" className="text-xs text-red-700">{cameraError}</p>}
                </>
              )}
            </div>

            <p className="text-xs text-text-muted">
              {resuming ? '' : 'Step 2: '}When you press the button below the screen goes full screen and the
              interview starts.
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
            <p className="text-sm text-text-muted">
              {endedReason ? 'Your interview has ended. Sending what you recorded…' : 'Your interview is finished. Wrapping up…'}
            </p>
          </div>
        )}

        {phase === 'uploading' && (
          <div className="rounded-xl border border-border bg-surface p-8 text-center space-y-5">
            <div>
              <p className="font-semibold text-text">
                {endedReason ? 'Your interview has ended.' : 'Your interview is finished.'}
              </p>
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
                {endedReason ? 'Your interview has ended' : 'Your interview is finished'}, but the recording hasn&apos;t uploaded yet.
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

        {phase === 'ended' && (
          <div className="rounded-xl border border-border bg-surface p-10 text-center space-y-4" data-testid="ended-screen">
            <AlertCircle size={40} className="text-amber-600 mx-auto" />
            <div className="space-y-2">
              <p className="font-semibold text-text">{endedMessage(endedReason).title}</p>
              {subtitle && <p className="text-xs text-text-muted">{subtitle}</p>}
              <p className="text-sm text-text-muted">{endedMessage(endedReason).body}</p>
              <p className="text-sm text-text-muted">{ENDED_FOOTER}</p>
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
