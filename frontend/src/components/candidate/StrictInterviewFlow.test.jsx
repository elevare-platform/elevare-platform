import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/interviewUpload', async (importOriginal) => ({
  ...(await importOriginal()),
  uploadRecording: vi.fn(async () => {}),
  putBlob: vi.fn(async () => {}),
}))
vi.mock('@/lib/strictInterview', async (importOriginal) => ({
  ...(await importOriginal()),
  checkDevice: vi.fn(() => ({ ok: true, problems: [] })),
}))

import { putBlob, uploadRecording } from '@/lib/interviewUpload'
import { checkDevice } from '@/lib/strictInterview'
import { STRICT_RULES_VERSION } from '@/lib/interviewRules'
import StrictInterviewFlow from './StrictInterviewFlow'

// ── Fakes for the parts of the browser the interview uses ───────────────────

class FakeMediaRecorder {
  static instances = []
  static isTypeSupported = () => true

  constructor(stream, options) {
    this.stream = stream
    this.mimeType = options?.mimeType
    this.state = 'inactive'
    FakeMediaRecorder.instances.push(this)
  }

  start() {
    this.state = 'recording'
  }

  // What the browser does once a second while recording.
  emit(data) {
    this.ondataavailable?.({ data })
  }

  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['audio-bytes'], { type: this.mimeType }) })
    this.onstop?.()
  }
}

class FakeMediaStream {
  constructor(tracks = []) {
    this.tracks = tracks
  }

  getTracks() { return this.tracks }
  getAudioTracks() { return this.tracks.filter((track) => track.kind === 'audio') }
  getVideoTracks() { return this.tracks.filter((track) => track.kind === 'video') }
}

function fakeCamera() {
  return new FakeMediaStream([
    { kind: 'audio', stop: vi.fn(), readyState: 'live' },
    { kind: 'video', stop: vi.fn(), readyState: 'live' },
  ])
}

let fullscreenElement = null
function setFullscreen(element) {
  fullscreenElement = element
  document.dispatchEvent(new Event('fullscreenchange'))
}

const FIRST = {
  interview_id: 'iv-1',
  finished: false,
  total_questions: 3,
  seconds_left_total: 1200,
  max_seconds_total: 1200,
  turn: { id: 't1', kind: 'QUESTION', number: 1, text: 'Tell us about a system you designed.', time_limit_seconds: 120, seconds_left: 120 },
}
const FOLLOW_UP = {
  ...FIRST,
  seconds_left_total: 1100,
  turn: { id: 't2', kind: 'FOLLOW_UP', number: 1, text: 'What would you change now?', time_limit_seconds: 90, seconds_left: 90 },
}
const SECOND = {
  ...FIRST,
  seconds_left_total: 1000,
  turn: { id: 't3', kind: 'QUESTION', number: 2, text: 'How did you handle your last outage?', time_limit_seconds: 120, seconds_left: 120 },
}
const FINISHED = { ...FIRST, finished: true, turn: null, seconds_left_total: 300 }

function setup(props = {}) {
  const handlers = {
    startInterview: vi.fn(async () => FIRST),
    sendAnswer: vi.fn(async () => SECOND),
    requestUploadUrl: vi.fn(),
    completeUpload: vi.fn(async () => {}),
  }
  const view = render(
    <MemoryRouter>
      <StrictInterviewFlow {...handlers} {...props} />
    </MemoryRouter>
  )
  return { ...handlers, ...view }
}

// The camera and microphone are checked on the first screen, before full screen.
async function allowCamera() {
  fireEvent.click(screen.getByRole('button', { name: 'Check my camera and microphone' }))
  await screen.findByText('Your camera and microphone are working.')
}

// For a candidate coming back to an interview already started: no rules to accept.
async function continueInterview() {
  await allowCamera()
  fireEvent.click(screen.getByRole('button', { name: 'Continue the interview' }))
}

async function acceptAndStart() {
  fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules/ }))
  await allowCamera()
  fireEvent.click(screen.getByRole('button', { name: 'Start the interview' }))
  await screen.findByTestId('question-text')
  // The question is on screen before React has attached the screen's listeners (its effects);
  // let those run, as they have by the time a person could press anything.
  await act(async () => {})
  // Leaving counts once the screen has been calm for a moment after the start: where the test
  // runs on a fake clock, let that moment pass, as it has by the time a person could leave.
  if (vi.isFakeTimers()) await act(async () => { await vi.advanceTimersByTimeAsync(1700) })
}

beforeEach(() => {
  FakeMediaRecorder.instances = []
  fullscreenElement = null
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
  vi.stubGlobal('MediaStream', FakeMediaStream)
  Object.defineProperty(document, 'fullscreenElement', { configurable: true, get: () => fullscreenElement })
  document.documentElement.requestFullscreen = vi.fn(async () => setFullscreen(document.documentElement))
  document.exitFullscreen = vi.fn(async () => setFullscreen(null))
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: vi.fn(async () => fakeCamera()) },
  })
  vi.mocked(checkDevice).mockReturnValue({ ok: true, problems: [] })
  vi.mocked(uploadRecording).mockClear()
  vi.mocked(putBlob).mockReset()
  vi.mocked(putBlob).mockResolvedValue(undefined)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

// ── Before the interview ────────────────────────────────────────────────────

describe('StrictInterviewFlow, before it starts', () => {
  it('shows the strict rules, and not the live interview rules', () => {
    setup()

    expect(screen.getByRole('heading', { name: 'AI video interview' })).toBeInTheDocument()
    expect(screen.getByText(/cannot be taken on a phone or a tablet/)).toBeInTheDocument()
    expect(screen.queryByText(/earphones or headphones/i)).not.toBeInTheDocument()
  })

  it('tells the candidate that leaving the screen is noted, warned about, and can end the interview', () => {
    setup()

    expect(screen.getByText(/The first three times you get a warning/)).toBeInTheDocument()
    expect(screen.getByText(/more than 60 seconds in total, ends the interview/)).toBeInTheDocument()
    expect(screen.getByText(/They do not end the interview/)).toBeInTheDocument()
    expect(screen.getByText(/press I need to stop and confirm/)).toBeInTheDocument()
  })

  it('says how to answer in three short lines before the rules, and the rule list has no repeated rule for it', () => {
    setup()

    const box = screen.getByTestId('how-to-answer')
    expect(box).toHaveTextContent('Say what you did yourself, as distinct from your team')
    expect(box).toHaveTextContent('say what you are assuming and why')
    expect(box).toHaveTextContent('same questions and is rated the same way')
    expect(box.querySelectorAll('li')).toHaveLength(3)
    // It comes before the rules the candidate accepts.
    expect(box.compareDocumentPosition(screen.getByTestId('interview-rules')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('keeps the rules short: a dozen numbered rules, not twenty, each in plain words', () => {
    setup()

    const items = within(screen.getByTestId('interview-rules')).getAllByRole('listitem')
    expect(items.length).toBeLessThanOrEqual(12)
    expect(items.length).toBeGreaterThanOrEqual(10)
    expect(screen.getByText(/The AI may ask one short follow-up/)).toBeInTheDocument()
    expect(screen.getByText(/Do not read a prepared text, use notes, a phone, a chatbot/)).toBeInTheDocument()
  })

  it('gives the 60 seconds away in total a rule of its own, highlighted, saying it can end it with no earlier warning', () => {
    setup()

    const rule = screen.getByText(/You have 60 seconds away from the screen in total/)
    expect(rule).toHaveTextContent('even if that is your first time leaving')
    expect(rule).toHaveTextContent('The screen shows how much you have used')
    expect(rule.closest('li').className).toContain('bg-amber-50')
  })

  it('will not start until the rules are accepted and the camera has been checked', async () => {
    setup()
    const start = screen.getByRole('button', { name: 'Start the interview' })

    expect(start).toBeDisabled()
    fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules/ }))
    expect(start).toBeDisabled()
    await allowCamera()
    expect(start).toBeEnabled()
  })

  it('will not start on a checked camera alone, without the rules accepted', async () => {
    setup()

    await allowCamera()

    expect(screen.getByRole('button', { name: 'Start the interview' })).toBeDisabled()
  })

  it('asks for the camera and microphone on this first screen, NOT after going full screen', async () => {
    setup()
    expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Check my camera and microphone' }))
    await screen.findByText('Your camera and microphone are working.')

    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledTimes(1)
    expect(document.documentElement.requestFullscreen).not.toHaveBeenCalled()
  })

  it('shows what the camera sees, so the candidate can check themselves', async () => {
    setup()

    await allowCamera()

    expect(document.querySelector('video')).toBeInTheDocument()
  })

  it('says what to do when the camera is blocked, and lets the candidate try again', async () => {
    navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockRejectedValueOnce(Object.assign(new Error('no'), { name: 'NotAllowedError' }))
      .mockResolvedValue(fakeCamera())
    setup()

    fireEvent.click(screen.getByRole('button', { name: 'Check my camera and microphone' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('blocked')
    expect(screen.getByRole('alert')).toHaveTextContent('camera icon in the address bar')
    expect(screen.getByRole('button', { name: 'Start the interview' })).toBeDisabled()
    await allowCamera()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('says so when the camera cannot be used for another reason', async () => {
    navigator.mediaDevices.getUserMedia = vi.fn(async () => {
      throw Object.assign(new Error('busy'), { name: 'NotReadableError' })
    })
    setup()

    fireEvent.click(screen.getByRole('button', { name: 'Check my camera and microphone' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('not in use by another app')
  })

  it('does not offer the camera check on a device that cannot take the interview', () => {
    vi.mocked(checkDevice).mockReturnValue({ ok: false, problems: [{ id: 'browser', message: 'Use Chrome or Edge.' }] })
    setup()

    expect(screen.getByRole('button', { name: 'Check my camera and microphone' })).toBeDisabled()
  })

  it('names every problem with the device and will not start', () => {
    vi.mocked(checkDevice).mockReturnValue({
      ok: false,
      problems: [
        { id: 'browser', message: 'Please open this link in the latest Chrome or Edge.' },
        { id: 'second-screen', message: 'A second screen is connected. Please disconnect it.' },
      ],
    })
    setup()
    fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules/ }))

    expect(screen.getAllByRole('alert')[0]).toHaveTextContent('latest Chrome or Edge')
    expect(screen.getAllByRole('alert')[0]).toHaveTextContent('second screen is connected')
    expect(screen.getByRole('button', { name: 'Start the interview' })).toBeDisabled()
  })

  it('welcomes a returning candidate back without asking for the rules again', () => {
    setup({ resuming: true })

    expect(screen.getByText(/You started this interview earlier/)).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue the interview' })).toBeDisabled()
  })

  it('lets a returning candidate continue once the camera has been checked', async () => {
    setup({ resuming: true })

    await allowCamera()

    expect(screen.getByRole('button', { name: 'Continue the interview' })).toBeEnabled()
  })

  it('shows a finished interview as submitted', () => {
    setup({ completed: true })

    expect(screen.getByText('Interview submitted')).toBeInTheDocument()
  })
})

// ── Starting ────────────────────────────────────────────────────────────────

describe('StrictInterviewFlow, starting', () => {
  it('goes full screen, opens the camera, starts on the server with the rules version, and shows the first question', async () => {
    const { startInterview } = setup()

    await acceptAndStart()

    expect(document.documentElement.requestFullscreen).toHaveBeenCalled()
    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled()
    expect(startInterview).toHaveBeenCalledWith({ accepted: true, rulesVersion: STRICT_RULES_VERSION })
    expect(screen.getByTestId('question-text')).toHaveTextContent('Tell us about a system you designed.')
    expect(screen.getByText('Question 1 of 3')).toBeInTheDocument()
    expect(screen.getByLabelText('Time left for this question')).toHaveTextContent('2:00')
  })

  it('records the whole interview and the first answer', async () => {
    setup()

    await acceptAndStart()

    const kinds = FakeMediaRecorder.instances.map((recorder) => recorder.mimeType)
    expect(kinds.some((type) => type.startsWith('video/webm'))).toBe(true)
    expect(kinds.some((type) => type.startsWith('audio/webm'))).toBe(true)
    expect(FakeMediaRecorder.instances.every((recorder) => recorder.state === 'recording')).toBe(true)
  })

  it('continues a started interview without needing the rules accepted again', async () => {
    const { startInterview } = setup({ resuming: true })

    await continueInterview()
    await screen.findByTestId('question-text')

    expect(startInterview).toHaveBeenCalled()
  })

  it('uses the camera it already checked and asks for nothing more once the interview starts', async () => {
    setup()

    await acceptAndStart()

    // Once, on the first screen. Starting does not ask again, so no pop-up can take the screen
    // out of full screen after it has started.
    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledTimes(1)
  })

  it('asks for the camera again only if the one it checked has stopped working', async () => {
    const first = fakeCamera()
    first.getTracks().forEach((track) => { track.readyState = 'ended' })
    navigator.mediaDevices.getUserMedia = vi.fn().mockResolvedValueOnce(first).mockResolvedValue(fakeCamera())
    setup()

    await acceptAndStart()

    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledTimes(2)
    expect(screen.getByTestId('question-text')).toBeInTheDocument()
  })

  it('says so when full screen is refused, gives the camera back, and does not start', async () => {
    const camera = fakeCamera()
    navigator.mediaDevices.getUserMedia = vi.fn(async () => camera)
    document.documentElement.requestFullscreen = vi.fn(async () => { throw new Error('denied') })
    const { startInterview } = setup()

    fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules/ }))
    await allowCamera()
    fireEvent.click(screen.getByRole('button', { name: 'Start the interview' }))

    expect(await screen.findByText(/needs full screen/)).toBeInTheDocument()
    expect(startInterview).not.toHaveBeenCalled()
    expect(camera.getTracks().every((track) => track.stop.mock.calls.length >= 1)).toBe(true)
  })

  it('asks for the camera again on the first screen after an error, since the check was undone', async () => {
    document.documentElement.requestFullscreen = vi.fn(async () => { throw new Error('denied') })
    setup()
    fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules/ }))
    await allowCamera()
    fireEvent.click(screen.getByRole('button', { name: 'Start the interview' }))
    await screen.findByText(/needs full screen/)

    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(screen.getByRole('button', { name: 'Start the interview' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Check my camera and microphone' })).toBeInTheDocument()
  })

  it("shows the server's own message when it refuses to start, and stops the camera", async () => {
    const camera = fakeCamera()
    navigator.mediaDevices.getUserMedia = vi.fn(async () => camera)
    const startInterview = vi.fn(async () => {
      throw { response: { data: { message: 'The questions for this interview are not ready. Please contact your recruiter.' } } }
    })
    setup({ startInterview })

    fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules/ }))
    await allowCamera()
    fireEvent.click(screen.getByRole('button', { name: 'Start the interview' }))

    expect(await screen.findByText(/questions for this interview are not ready/)).toBeInTheDocument()
    expect(camera.getTracks().every((track) => track.stop.mock.calls.length === 1)).toBe(true)
  })
})

// ── Answering ───────────────────────────────────────────────────────────────

describe('StrictInterviewFlow, answering', () => {
  it('sends the spoken answer for the question on screen and shows the next question', async () => {
    const { sendAnswer } = setup()
    await acceptAndStart()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByTestId('question-text')).toHaveTextContent('How did you handle your last outage?'))
    expect(sendAnswer).toHaveBeenCalledTimes(1)
    const [turnId, blob] = sendAnswer.mock.calls[0]
    expect(turnId).toBe('t1')
    expect(blob).toBeInstanceOf(Blob)
    expect(blob.size).toBeGreaterThan(0)
    expect(screen.getByText('Question 2 of 3')).toBeInTheDocument()
  })

  it('shows a follow-up as a follow-up to its question', async () => {
    const sendAnswer = vi.fn(async () => FOLLOW_UP)
    setup({ sendAnswer })
    await acceptAndStart()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByText('Follow-up to question 1')).toBeInTheDocument()
    expect(screen.getByTestId('question-text')).toHaveTextContent('What would you change now?')
    expect(screen.getByLabelText('Time left for this question')).toHaveTextContent('1:30')
  })

  it('sends one answer however often Next is pressed', async () => {
    let release
    const sendAnswer = vi.fn(() => new Promise((resolve) => { release = () => resolve(SECOND) }))
    setup({ sendAnswer })
    await acceptAndStart()
    const next = screen.getByRole('button', { name: 'Next' })

    fireEvent.click(next)
    fireEvent.click(next)
    fireEvent.click(next)
    await screen.findByText('Sending your answer…')
    release()
    await screen.findByText('Question 2 of 3')

    expect(sendAnswer).toHaveBeenCalledTimes(1)
  })

  it('keeps the recorded answer when sending fails, and sends the same one again on request', async () => {
    const sendAnswer = vi
      .fn()
      .mockRejectedValueOnce({ response: { status: 422, data: { message: 'That recording is too large.' } } })
      .mockResolvedValueOnce(SECOND)
    setup({ sendAnswer })
    await acceptAndStart()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('That recording is too large.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await screen.findByText('Question 2 of 3')

    expect(sendAnswer).toHaveBeenCalledTimes(2)
    expect(sendAnswer.mock.calls[1][0]).toBe('t1')
    expect(sendAnswer.mock.calls[1][1]).toBe(sendAnswer.mock.calls[0][1])
  })

  it('sends the answer by itself when the time for the question runs out', async () => {
    vi.useFakeTimers()
    const sendAnswer = vi.fn(async () => SECOND)
    setup({ sendAnswer })
    fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Check my camera and microphone' }))
    await act(async () => { await vi.advanceTimersByTimeAsync(10) })
    fireEvent.click(screen.getByRole('button', { name: 'Start the interview' }))
    await act(async () => { await vi.advanceTimersByTimeAsync(10) })
    expect(screen.getByTestId('question-text')).toBeInTheDocument()

    await act(async () => { await vi.advanceTimersByTimeAsync(119_000) })
    expect(sendAnswer).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Time left for this question')).toHaveTextContent('0:01')

    await act(async () => { await vi.advanceTimersByTimeAsync(2_000) })
    expect(sendAnswer).toHaveBeenCalledTimes(1)
    expect(sendAnswer.mock.calls[0][0]).toBe('t1')
  })

  it('counts down from the time the server says is left, not from the full allowance', async () => {
    const startInterview = vi.fn(async () => ({ ...FIRST, turn: { ...FIRST.turn, seconds_left: 47 } }))
    setup({ startInterview })

    await acceptAndStart()

    expect(screen.getByLabelText('Time left for this question')).toHaveTextContent('0:47')
  })
})

// ── Finishing ───────────────────────────────────────────────────────────────

describe('StrictInterviewFlow, finishing', () => {
  it('uploads the recording and completes the interview after the last answer', async () => {
    const sendAnswer = vi.fn(async () => FINISHED)
    const { completeUpload, requestUploadUrl } = setup({ sendAnswer })
    await acceptAndStart()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByText('Interview submitted')).toBeInTheDocument()
    expect(uploadRecording).toHaveBeenCalledTimes(1)
    expect(uploadRecording.mock.calls[0][0]).toMatchObject({ requestUploadUrl, contentType: 'video/webm' })
    expect(uploadRecording.mock.calls[0][0].blob.size).toBeGreaterThan(0)
    expect(completeUpload).toHaveBeenCalledTimes(1)
    expect(document.exitFullscreen).toHaveBeenCalled()
  })

  it('stops the camera once the questions are over', async () => {
    const camera = fakeCamera()
    navigator.mediaDevices.getUserMedia = vi.fn(async () => camera)
    setup({ sendAnswer: vi.fn(async () => FINISHED) })
    await acceptAndStart()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    await screen.findByText('Interview submitted')

    expect(camera.getTracks().every((track) => track.stop.mock.calls.length >= 1)).toBe(true)
  })

  it('lets the candidate retry the upload without redoing the interview', async () => {
    uploadRecording.mockRejectedValueOnce({ response: { status: 422, data: { message: 'We did not receive your recording.' } } })
    const { completeUpload } = setup({ sendAnswer: vi.fn(async () => FINISHED) })
    await acceptAndStart()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText(/hasn.t uploaded yet/)).toBeInTheDocument()
    expect(screen.getByText('We did not receive your recording.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry upload' }))

    expect(await screen.findByText('Interview submitted')).toBeInTheDocument()
    expect(uploadRecording).toHaveBeenCalledTimes(2)
    expect(uploadRecording.mock.calls[1][0].blob).toBe(uploadRecording.mock.calls[0][0].blob)
    expect(completeUpload).toHaveBeenCalledTimes(1)
  })

  it('goes straight to sending the recording when a returning candidate finds the time was up', async () => {
    const startInterview = vi.fn(async () => FINISHED)
    const { completeUpload } = setup({ startInterview, resuming: true })

    await continueInterview()

    expect(await screen.findByText('Interview submitted')).toBeInTheDocument()
    expect(completeUpload).toHaveBeenCalledTimes(1)
  })
})

// ── The locked screen ───────────────────────────────────────────────────────

describe('StrictInterviewFlow, the locked screen', () => {
  it('switches off right-click, copy, cut, paste, selecting and dragging while it runs', async () => {
    setup()
    await acceptAndStart()

    for (const name of ['contextmenu', 'copy', 'cut', 'paste', 'selectstart', 'dragstart']) {
      const event = new Event(name, { cancelable: true, bubbles: true })
      document.body.dispatchEvent(event)
      expect(event.defaultPrevented, name).toBe(true)
    }
  })

  it('blocks the shortcuts that open, close or switch tabs, and leaves plain keys alone', async () => {
    setup()
    await acceptAndStart()

    const press = (init) => {
      const event = new KeyboardEvent('keydown', { cancelable: true, bubbles: true, ...init })
      document.body.dispatchEvent(event)
      return event.defaultPrevented
    }

    expect(press({ key: 't', ctrlKey: true })).toBe(true)
    expect(press({ key: 'w', ctrlKey: true })).toBe(true)
    expect(press({ key: 'Tab', altKey: true })).toBe(true)
    expect(press({ key: 'F12' })).toBe(true)
    expect(press({ key: 'Tab' })).toBe(false)
    expect(press({ key: 'Enter' })).toBe(false)
  })

  it('leaves right-click and shortcuts alone before the interview starts', () => {
    setup()

    const event = new Event('contextmenu', { cancelable: true, bubbles: true })
    document.body.dispatchEvent(event)

    expect(event.defaultPrevented).toBe(false)
  })

  it('puts a block over the question when full screen is left, and removes it on return', async () => {
    setup()
    await acceptAndStart()
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()

    act(() => setFullscreen(null))
    expect(screen.getByRole('alertdialog', { name: 'Return to full screen' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Return to full screen' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument())
  })

  it('asks the browser to confirm before the page is closed or reloaded', async () => {
    setup()
    await acceptAndStart()

    const event = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(event)

    expect(event.defaultPrevented).toBe(true)
  })

  it('does not interfere with closing the page before the interview starts', () => {
    setup()

    const event = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(event)

    expect(event.defaultPrevented).toBe(false)
  })
})

// ── Not losing the recording to a reload ────────────────────────────────────

// A store in memory with the same methods as the real one (lib/recordingStore.js).
function memoryStore(initial = {}) {
  const chunks = new Map(Object.entries(initial)) // `${interviewId}/${segment}` -> Blob[]
  const key = (interviewId, segment) => `${interviewId}/${segment}`
  return {
    chunks,
    addChunk: vi.fn(async (interviewId, segment, index, blob) => {
      const list = chunks.get(key(interviewId, segment)) ?? []
      list[index] = blob
      chunks.set(key(interviewId, segment), list)
      return true
    }),
    segments: vi.fn(async (interviewId) =>
      [...chunks.entries()]
        .filter(([k]) => k.startsWith(`${interviewId}/`))
        .map(([k, list]) => ({ segment: k.split('/')[1], chunks: list.length, bytes: list.reduce((n, b) => n + b.size, 0) }))
    ),
    readSegment: vi.fn(async (interviewId, segment) => chunks.get(key(interviewId, segment)) ?? []),
    deleteSegment: vi.fn(async (interviewId, segment) => {
      chunks.delete(key(interviewId, segment))
      return true
    }),
    deleteInterview: vi.fn(async (interviewId) => {
      for (const k of [...chunks.keys()]) if (k.startsWith(`${interviewId}/`)) chunks.delete(k)
      return true
    }),
  }
}

const EARLIER = new Blob(['E'.repeat(3000)], { type: 'video/webm' })

describe('StrictInterviewFlow, keeping the recording across a reload', () => {
  const interviewRecorder = () => FakeMediaRecorder.instances.find((r) => r.mimeType.startsWith('video/'))

  it('keeps every chunk of the recording in storage as it is made, in order, under the interview', async () => {
    const recordingStore = memoryStore()
    setup({ recordingStore })
    await acceptAndStart()

    const first = new Blob(['one'])
    const second = new Blob(['two'])
    interviewRecorder().emit(first)
    interviewRecorder().emit(second)

    await waitFor(() => expect(recordingStore.addChunk).toHaveBeenCalledTimes(2))
    const [id1, segment1, index1, blob1] = recordingStore.addChunk.mock.calls[0]
    const [id2, segment2, index2, blob2] = recordingStore.addChunk.mock.calls[1]
    expect([id1, id2]).toEqual(['iv-1', 'iv-1'])
    expect(segment1).toBe(segment2)
    expect([index1, index2]).toEqual([0, 1])
    expect([blob1, blob2]).toEqual([first, second])
  })

  it('does not keep the empty chunks the recorder sometimes emits', async () => {
    const recordingStore = memoryStore()
    setup({ recordingStore })
    await acceptAndStart()

    interviewRecorder().emit(new Blob([]))

    expect(recordingStore.addChunk).not.toHaveBeenCalled()
  })

  it('sends a recording left by an earlier visit as a part, and forgets it, while the interview carries on', async () => {
    const recordingStore = memoryStore({ 'iv-1/before-reload': [EARLIER] })
    const requestPartUploadUrl = vi.fn(async () => ({ upload_url: 'https://r2.test/part-1', part: 1 }))
    setup({ recordingStore, requestPartUploadUrl, resuming: true })

    await continueInterview()
    await screen.findByTestId('question-text')

    await waitFor(() => expect(putBlob).toHaveBeenCalledTimes(1))
    expect(requestPartUploadUrl).toHaveBeenCalledTimes(1)
    expect(putBlob.mock.calls[0][0]).toMatchObject({ url: 'https://r2.test/part-1', contentType: 'video/webm' })
    expect(putBlob.mock.calls[0][0].blob.size).toBe(3000)
    await waitFor(() => expect(recordingStore.deleteSegment).toHaveBeenCalledWith('iv-1', 'before-reload'))
    // The question is on screen the whole time: sending the old recording does not hold it up.
    expect(screen.getByTestId('question-text')).toBeInTheDocument()
  })

  it('never sends the recording it is making now as a part', async () => {
    const recordingStore = memoryStore()
    const requestPartUploadUrl = vi.fn(async () => ({ upload_url: 'https://r2.test/part', part: 1 }))
    setup({ recordingStore, requestPartUploadUrl })
    await acceptAndStart()

    interviewRecorder().emit(new Blob(['N'.repeat(3000)]))
    await waitFor(() => expect(recordingStore.addChunk).toHaveBeenCalled())

    expect(requestPartUploadUrl).not.toHaveBeenCalled()
    expect(putBlob).not.toHaveBeenCalled()
  })

  it('waits for the earlier recording to reach the server before it completes the interview', async () => {
    const recordingStore = memoryStore({ 'iv-1/before-reload': [EARLIER] })
    let releasePart
    const requestPartUploadUrl = vi.fn(() => new Promise((resolve) => {
      releasePart = () => resolve({ upload_url: 'https://r2.test/part-1', part: 1 })
    }))
    const { completeUpload } = setup({
      recordingStore,
      requestPartUploadUrl,
      resuming: true,
      sendAnswer: vi.fn(async () => FINISHED),
    })
    await continueInterview()
    await screen.findByTestId('question-text')

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    await screen.findByText(/Wrapping up/)
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)) })
    expect(completeUpload).not.toHaveBeenCalled()
    expect(uploadRecording).not.toHaveBeenCalled()

    releasePart()
    expect(await screen.findByText('Interview submitted')).toBeInTheDocument()
    expect(putBlob).toHaveBeenCalledTimes(1)
    expect(completeUpload).toHaveBeenCalledTimes(1)
  })

  it('still completes the interview when the earlier recording cannot be sent, and keeps it for next time', async () => {
    const recordingStore = memoryStore({ 'iv-1/before-reload': [EARLIER] })
    const requestPartUploadUrl = vi.fn(async () => {
      throw { response: { status: 422, data: { code: 'INTERVIEW_TOO_MANY_PARTS' } } }
    })
    const { completeUpload } = setup({
      recordingStore,
      requestPartUploadUrl,
      resuming: true,
      sendAnswer: vi.fn(async () => FINISHED),
    })
    await continueInterview()
    await screen.findByTestId('question-text')

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByText('Interview submitted')).toBeInTheDocument()
    expect(completeUpload).toHaveBeenCalledTimes(1)
  })

  it('forgets everything it kept once the interview is submitted', async () => {
    const recordingStore = memoryStore()
    setup({ recordingStore, sendAnswer: vi.fn(async () => FINISHED) })
    await acceptAndStart()
    interviewRecorder().emit(new Blob(['x'.repeat(10)]))

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    await screen.findByText('Interview submitted')

    expect(recordingStore.deleteInterview).toHaveBeenCalledWith('iv-1')
  })

  it('keeps what it recorded while the upload fails, so a reload can still send it', async () => {
    uploadRecording.mockRejectedValueOnce({ response: { status: 422, data: { message: 'We did not receive your recording.' } } })
    const recordingStore = memoryStore()
    setup({ recordingStore, sendAnswer: vi.fn(async () => FINISHED) })
    await acceptAndStart()
    interviewRecorder().emit(new Blob(['x'.repeat(10)]))

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    await screen.findByText(/hasn.t uploaded yet/)

    expect(recordingStore.deleteInterview).not.toHaveBeenCalled()
    await waitFor(() => expect(recordingStore.chunks.size).toBe(1))
  })

  it('records in memory only, as before, when the browser has no storage', async () => {
    const sendAnswer = vi.fn(async () => FINISHED)
    setup({ recordingStore: null, sendAnswer })
    await acceptAndStart()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByText('Interview submitted')).toBeInTheDocument()
    expect(uploadRecording.mock.calls[0][0].blob.size).toBeGreaterThan(0)
  })
})

// ── Leaving, warnings, ending, stopping ─────────────────────────────────────

const CONDUCT = { leaves: 0, max_leaves: 4, away_seconds: 0, max_away_seconds: 60, key_presses: 0, ended: null }
const reply = (over = {}) => ({ ...FIRST, ...CONDUCT, ...over })
const ENDED = (reason) => ({ ...FIRST, ...CONDUCT, ended: reason, turn: null, finished: false })

let focused
function setFocus(value) {
  focused = value
}
function away(cause = 'FULLSCREEN') {
  if (cause === 'FULLSCREEN') act(() => setFullscreen(null))
  if (cause === 'BLUR') {
    setFocus(false)
    act(() => { window.dispatchEvent(new Event('blur')) })
  }
}
function back() {
  setFocus(true)
  act(() => {
    window.dispatchEvent(new Event('focus'))
    setFullscreen(document.documentElement)
  })
}

describe('StrictInterviewFlow, leaving the screen', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    setFocus(true)
    document.hasFocus = () => focused
  })

  async function running(props = {}) {
    const reportEvent = vi.fn(async () => reply())
    const handlers = setup({ reportEvent, ...props })
    await acceptAndStart()
    return { reportEvent, ...handlers }
  }

  const wait = (ms) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })

  it('tells the server after a second away, with the cause, and again when the candidate is back', async () => {
    const { reportEvent } = await running()

    away('BLUR')
    await wait(1100)
    expect(reportEvent).toHaveBeenCalledWith({ type: 'left', cause: 'BLUR' })
    back()
    await wait(10)

    expect(reportEvent).toHaveBeenCalledWith({ type: 'returned' })
  })

  it('says nothing about a blip shorter than a second', async () => {
    const { reportEvent } = await running()

    away('BLUR')
    await wait(400)
    back()
    await wait(3000)

    expect(reportEvent).not.toHaveBeenCalledWith({ type: 'left', cause: 'BLUR' })
    expect(reportEvent).not.toHaveBeenCalledWith({ type: 'returned' })
  })

  it('warns the candidate on their return, with how many warnings and how much time are used', async () => {
    const reportEvent = vi.fn(async (body) =>
      body.type === 'returned' ? reply({ leaves: 2, away_seconds: 31 }) : reply({ leaves: 2 })
    )
    setup({ reportEvent })
    await acceptAndStart()

    away('FULLSCREEN')
    await wait(1100)
    back()
    await wait(10)

    const box = await screen.findByRole('alertdialog', { name: 'You left the interview screen' })
    expect(within(box).getByTestId('leave-warning-count')).toHaveTextContent('Warning 2 of 3')
    expect(box).toHaveTextContent('If you leave it 2 more times')
    expect(box).toHaveTextContent('more than 29 more seconds in total')
    expect(box).toHaveTextContent('The time for your question is still running')
    expect(screen.getByTestId('warnings-used')).toHaveTextContent('Warnings used: 2 of 3')
    expect(screen.getByTestId('away-time')).toHaveTextContent('Time away from this screen: 31 of 60 seconds in total')
    // The box itself shows the time used, with a bar.
    expect(within(box).getByTestId('leave-away-used')).toHaveTextContent('Time away used: 31 of 60 seconds')
    expect(within(box).getByRole('progressbar', { name: 'Time away used' })).toHaveAttribute('aria-valuenow', '31')
  })

  it('shows the 60 second limit on screen from the start, before any leave, in a calm colour', async () => {
    await running({ startInterview: vi.fn().mockResolvedValue(reply()) })

    const line = await screen.findByTestId('away-time')
    expect(line).toHaveTextContent('Time away from this screen: 0 of 60 seconds in total. At 60 the interview ends.')
    expect(line.className).toContain('text-text-muted')
    expect(screen.queryByTestId('warnings-used')).not.toBeInTheDocument()
  })


  it('dims the screen with a box the moment the candidate is back, before the server has replied', async () => {
    let release
    const reportEvent = vi.fn((body) =>
      body.type === 'returned'
        ? new Promise((resolve) => { release = () => resolve(reply({ leaves: 1, away_seconds: 5 })) })
        : Promise.resolve(reply())
    )
    setup({ reportEvent })
    await acceptAndStart()

    away('BLUR')
    await wait(1100)
    back()
    await wait(10)

    const box = screen.getByRole('alertdialog', { name: 'You left the interview screen' })
    expect(box).toHaveTextContent('Checking how many warnings you have used')
    expect(within(box).getByRole('button', { name: /I understand/ })).toBeDisabled()
    await act(async () => { release() })
    expect(within(box).getByRole('button', { name: /I understand/ })).toBeEnabled()
    expect(within(box).getByTestId('leave-warning-count')).toHaveTextContent('Warning 1 of 3')
  })

  it('does not show the box for a blip shorter than a second', async () => {
    await running()

    away('BLUR')
    await wait(400)
    back()
    await wait(200)

    expect(screen.queryByRole('alertdialog', { name: 'You left the interview screen' })).not.toBeInTheDocument()
  })

  it('stays until the candidate confirms it, and does not take itself down', async () => {
    const reportEvent = vi.fn(async (body) => (body.type === 'returned' ? reply({ leaves: 1, away_seconds: 3 }) : reply()))
    setup({ reportEvent })
    await acceptAndStart()
    away('BLUR')
    await wait(1100)
    back()
    await wait(10)
    await screen.findByRole('alertdialog', { name: 'You left the interview screen' })

    await wait(60_000)

    expect(screen.getByRole('alertdialog', { name: 'You left the interview screen' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /I understand, go back to the interview/ }))
    expect(screen.queryByRole('alertdialog', { name: 'You left the interview screen' })).not.toBeInTheDocument()
  })

  it('says plainly that it is the last warning when the next leave would end the interview', async () => {
    const reportEvent = vi.fn(async (body) =>
      body.type === 'returned' ? reply({ leaves: 3, away_seconds: 30 }) : reply({ leaves: 3 })
    )
    setup({ reportEvent })
    await acceptAndStart()
    away('BLUR')
    await wait(1100)
    back()
    await wait(10)

    const box = await screen.findByRole('alertdialog', { name: 'You left the interview screen' })
    expect(within(box).getByTestId('leave-warning-count')).toHaveTextContent('Warning 3 of 3')
    expect(box).toHaveTextContent('This was your last warning')
    expect(box).toHaveTextContent('If you leave the screen again')
  })

  it('still tells the candidate to stay when the server could not be reached', async () => {
    const reportEvent = vi.fn(async (body) => {
      if (body.type === 'returned') throw { response: { status: 422 } }
      return reply()
    })
    setup({ reportEvent })
    await acceptAndStart()
    away('BLUR')
    await wait(1100)
    back()
    await wait(10)

    const box = await screen.findByRole('alertdialog', { name: 'You left the interview screen' })
    expect(box).toHaveTextContent('Please stay on this screen')
    expect(within(box).getByRole('button', { name: /I understand/ })).toBeEnabled()
  })

  it('takes the box away when the interview has ended', async () => {
    const reportEvent = vi.fn(async (body) => (body.type === 'returned' ? ENDED('TOO_LONG_AWAY') : reply()))
    setup({ reportEvent })
    await acceptAndStart()
    away('BLUR')
    await wait(1100)
    back()
    await wait(10)

    expect(await screen.findByTestId('ended-screen')).toBeInTheDocument()
    expect(screen.queryByRole('alertdialog', { name: 'You left the interview screen' })).not.toBeInTheDocument()
  })

  it('changes the tab title while the candidate is on another tab, and puts it back', async () => {
    document.title = 'Elevare'
    await running()

    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' })
    act(() => { document.dispatchEvent(new Event('visibilitychange')) })
    expect(document.title).toBe('Return to your interview')

    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' })
    act(() => { document.dispatchEvent(new Event('visibilitychange')) })
    expect(document.title).toBe('Elevare')
  })

  it('does not count what happens while the interview is starting, such as a browser pop-up', async () => {
    const reportEvent = vi.fn(async () => reply())
    setup({ reportEvent })
    fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules/ }))
    await allowCamera()
    // Full screen takes effect, then a pop-up takes it away straight after the interview starts.
    document.documentElement.requestFullscreen = vi.fn(async () => {
      setFullscreen(document.documentElement)
      setTimeout(() => setFullscreen(null), 5)
    })
    fireEvent.click(screen.getByRole('button', { name: 'Start the interview' }))
    await screen.findByTestId('question-text')
    // The pop-up is up for longer than the second after which a leave would be reported, and
    // well inside the 15 seconds after which the watch starts regardless (the test's real time
    // also runs the fake clock, so there is room to spare).
    await wait(2500)

    // Back in full screen.
    act(() => setFullscreen(document.documentElement))
    await wait(2000)

    expect(reportEvent.mock.calls.filter(([body]) => body.type === 'left')).toHaveLength(0)
    expect(screen.queryByRole('alertdialog', { name: 'You left the interview screen' })).not.toBeInTheDocument()
  })

  it('does count a candidate who never returns to full screen after it starts', async () => {
    const reportEvent = vi.fn(async () => reply())
    setup({ reportEvent })
    fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules/ }))
    await allowCamera()
    document.documentElement.requestFullscreen = vi.fn(async () => {
      setFullscreen(document.documentElement)
      setTimeout(() => setFullscreen(null), 5)
    })
    fireEvent.click(screen.getByRole('button', { name: 'Start the interview' }))
    await screen.findByTestId('question-text')

    await wait(17_000)

    expect(reportEvent).toHaveBeenCalledWith({ type: 'left', cause: 'FULLSCREEN' })
  })

  it('ends the interview, sends what was recorded, and says so when the server says it ended', async () => {
    const reportEvent = vi.fn(async (body) => (body.type === 'left' ? ENDED('TOO_MANY_LEAVES') : reply()))
    const { completeUpload } = setup({ reportEvent })
    await acceptAndStart()

    away('FULLSCREEN')
    await wait(1100)

    expect(await screen.findByTestId('ended-screen')).toBeInTheDocument()
    expect(screen.getByText('Your interview has ended')).toBeInTheDocument()
    expect(screen.getByText(/too many times/)).toBeInTheDocument()
    expect(screen.getByText(/contact the employer who invited you/)).toBeInTheDocument()
    expect(screen.queryByText('Interview submitted')).not.toBeInTheDocument()
    // The recording and the answers are still sent: the employer reviews them.
    expect(uploadRecording).toHaveBeenCalledTimes(1)
    expect(uploadRecording.mock.calls[0][0].blob.size).toBeGreaterThan(0)
    expect(completeUpload).toHaveBeenCalledTimes(1)
  })

  it('says the time away was the reason when that is what ended it', async () => {
    const reportEvent = vi.fn(async (body) => (body.type === 'returned' ? ENDED('TOO_LONG_AWAY') : reply()))
    setup({ reportEvent })
    await acceptAndStart()
    away('BLUR')
    await wait(1100)
    back()
    await wait(10)

    expect(await screen.findByText(/away from the interview screen for too long/)).toBeInTheDocument()
  })

  it('stops the camera and the recording once it has ended, and leaves full screen', async () => {
    const camera = fakeCamera()
    navigator.mediaDevices.getUserMedia = vi.fn(async () => camera)
    const reportEvent = vi.fn(async (body) => (body.type === 'left' ? ENDED('TOO_MANY_LEAVES') : reply()))
    setup({ reportEvent })
    await acceptAndStart()

    away('FULLSCREEN')
    await wait(1100)
    await screen.findByTestId('ended-screen')

    expect(camera.getTracks().every((track) => track.stop.mock.calls.length >= 1)).toBe(true)
    expect(FakeMediaRecorder.instances.every((recorder) => recorder.state === 'inactive')).toBe(true)
  })

  it('reports nothing more once the interview has ended', async () => {
    const reportEvent = vi.fn(async (body) => (body.type === 'left' ? ENDED('TOO_MANY_LEAVES') : reply()))
    setup({ reportEvent })
    await acceptAndStart()
    away('FULLSCREEN')
    await wait(1100)
    await screen.findByTestId('ended-screen')
    const calls = reportEvent.mock.calls.length

    back()
    away('BLUR')
    await wait(20_000)

    expect(reportEvent).toHaveBeenCalledTimes(calls)
  })

  it('retries telling the server it is back, since the server keeps counting a leave until it hears', async () => {
    const reportEvent = vi
      .fn()
      .mockResolvedValueOnce(reply()) // left
      .mockRejectedValueOnce(new Error('network')) // returned, first try
      .mockResolvedValue(reply({ leaves: 1 }))
    setup({ reportEvent })
    await acceptAndStart()

    away('BLUR')
    await wait(1100)
    back()
    await wait(3000)

    expect(reportEvent.mock.calls.filter(([body]) => body.type === 'returned')).toHaveLength(2)
  })

  it('carries on when telling the server fails, and does not show an error for it', async () => {
    const reportEvent = vi.fn(async () => { throw new Error('network') })
    setup({ reportEvent })
    await acceptAndStart()

    away('BLUR')
    await wait(1100)

    expect(screen.getByTestId('question-text')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('says it is still there every 15 seconds', async () => {
    const { reportEvent } = await running()

    await wait(15_100)
    await wait(15_000)

    expect(reportEvent.mock.calls.filter(([body]) => body.type === 'ping').length).toBeGreaterThanOrEqual(2)
  })

  it('watches nothing when the screen was given no way to report', async () => {
    setup()
    await acceptAndStart()

    away('BLUR')
    await wait(5000)

    expect(screen.getByTestId('question-text')).toBeInTheDocument()
  })
})

describe('StrictInterviewFlow, key presses that try to leave', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    setFocus(true)
    document.hasFocus = () => focused
  })

  const press = (init) => {
    const event = new KeyboardEvent('keydown', { cancelable: true, bubbles: true, ...init })
    act(() => { document.body.dispatchEvent(event) })
    return event
  }

  async function running() {
    const reportEvent = vi.fn(async () => reply({ key_presses: 1 }))
    setup({ reportEvent })
    await acceptAndStart()
    return reportEvent
  }

  it('reports Escape and warns, without ending the interview', async () => {
    const reportEvent = await running()

    press({ key: 'Escape' })

    expect(reportEvent).toHaveBeenCalledWith({ type: 'key', key: 'Escape' })
    expect(await screen.findByRole('status')).toHaveTextContent('does not end the interview')
    expect(screen.getByTestId('question-text')).toBeInTheDocument()
  })

  it.each([
    [{ key: 'F12' }, 'F12'],
    [{ key: 'Alt' }, 'Alt'],
    [{ key: 't', ctrlKey: true }, 'Ctrl+T'],
    [{ key: 'Tab', ctrlKey: true }, 'Ctrl+Tab'],
  ])('reports %j as %s', async (init, name) => {
    const reportEvent = await running()

    press(init)

    expect(reportEvent).toHaveBeenCalledWith({ type: 'key', key: name })
  })

  it('still blocks the key as well as reporting it', async () => {
    await running()

    expect(press({ key: 't', ctrlKey: true }).defaultPrevented).toBe(true)
  })

  it('reports a held key once, not for every repeat', async () => {
    const reportEvent = await running()

    for (let i = 0; i < 8; i += 1) press({ key: 'Escape', repeat: true })

    expect(reportEvent.mock.calls.filter(([body]) => body.type === 'key')).toHaveLength(1)
  })

  it('reports the same key again after a couple of seconds', async () => {
    const reportEvent = await running()

    press({ key: 'Escape' })
    await act(async () => { await vi.advanceTimersByTimeAsync(2500) })
    press({ key: 'Escape' })

    expect(reportEvent.mock.calls.filter(([body]) => body.type === 'key')).toHaveLength(2)
  })

  it('does not report ordinary keys, or Ctrl or Shift pressed by themselves', async () => {
    const reportEvent = await running()

    press({ key: 'a' })
    press({ key: 'Enter' })
    press({ key: 'Tab' })
    press({ key: 'Shift', shiftKey: true })
    press({ key: 'Control', ctrlKey: true })

    expect(reportEvent.mock.calls.filter(([body]) => body.type === 'key')).toHaveLength(0)
  })

  it.each([
    [{ key: 'I', ctrlKey: true, shiftKey: true }, 'Ctrl+Shift+I'],
    [{ key: 'Tab', altKey: true }, 'Alt+Tab'],
    [{ key: 'c', ctrlKey: true }, 'Ctrl+C'],
    [{ key: 'v', ctrlKey: true }, 'Ctrl+V'],
    [{ key: 'l', metaKey: true }, 'Meta+L'],
  ])('reports the full combination %j as %s, not just its first key', async (init, name) => {
    const reportEvent = await running()

    press(init)

    expect(reportEvent).toHaveBeenCalledWith({ type: 'key', key: name })
  })
})

describe('StrictInterviewFlow, "I need to stop"', () => {
  beforeEach(() => {
    setFocus(true)
    document.hasFocus = () => focused
  })

  async function running(props = {}) {
    const stopInterview = vi.fn(async () => ENDED('STOPPED'))
    const reportEvent = vi.fn(async () => reply())
    const handlers = setup({ stopInterview, reportEvent, ...props })
    await acceptAndStart()
    return { stopInterview, reportEvent, ...handlers }
  }

  it('has a small button, and asks before it stops anything', async () => {
    const { stopInterview } = await running()

    fireEvent.click(screen.getByRole('button', { name: 'I need to stop' }))

    expect(screen.getByRole('alertdialog', { name: 'Stop the interview' })).toBeInTheDocument()
    expect(stopInterview).not.toHaveBeenCalled()
  })

  it('does not use the browsers own confirm box, which would take the page out of full screen', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    await running()

    fireEvent.click(screen.getByRole('button', { name: 'I need to stop' }))
    fireEvent.click(screen.getByRole('button', { name: 'Stop the interview' }))

    expect(confirm).not.toHaveBeenCalled()
    confirm.mockRestore()
  })

  it('goes back to the question when the candidate keeps going', async () => {
    const { stopInterview } = await running()
    fireEvent.click(screen.getByRole('button', { name: 'I need to stop' }))

    fireEvent.click(screen.getByRole('button', { name: 'Keep going' }))

    expect(screen.queryByRole('alertdialog', { name: 'Stop the interview' })).not.toBeInTheDocument()
    expect(stopInterview).not.toHaveBeenCalled()
    expect(screen.getByTestId('question-text')).toBeInTheDocument()
  })

  it('ends the interview as the candidates own choice, sends the recording and says so', async () => {
    const { stopInterview, completeUpload } = await running()
    fireEvent.click(screen.getByRole('button', { name: 'I need to stop' }))

    fireEvent.click(screen.getByRole('button', { name: 'Stop the interview' }))

    expect(await screen.findByTestId('ended-screen')).toBeInTheDocument()
    expect(screen.getByText('You stopped the interview')).toBeInTheDocument()
    expect(screen.getByText(/The employer has been told/)).toBeInTheDocument()
    expect(stopInterview).toHaveBeenCalledTimes(1)
    expect(uploadRecording).toHaveBeenCalledTimes(1)
    expect(completeUpload).toHaveBeenCalledTimes(1)
  })

  it('stays on the question and says so when stopping fails', async () => {
    const stopInterview = vi.fn(async () => {
      throw { response: { data: { message: 'We could not stop the interview. Please try again.' } } }
    })
    await running({ stopInterview })
    fireEvent.click(screen.getByRole('button', { name: 'I need to stop' }))

    fireEvent.click(screen.getByRole('button', { name: 'Stop the interview' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('We could not stop the interview')
    expect(screen.getByRole('alertdialog', { name: 'Stop the interview' })).toBeInTheDocument()
    expect(uploadRecording).not.toHaveBeenCalled()
  })

  it('is not offered when the screen was given no way to stop', async () => {
    setup()
    await acceptAndStart()

    expect(screen.queryByRole('button', { name: 'I need to stop' })).not.toBeInTheDocument()
  })

  it('is not offered while an answer is being sent', async () => {
    let release
    const sendAnswer = vi.fn(() => new Promise((resolve) => { release = () => resolve(SECOND) }))
    setup({ stopInterview: vi.fn(), sendAnswer })
    await acceptAndStart()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    await screen.findByText('Sending your answer…')

    expect(screen.getByRole('button', { name: 'I need to stop' })).toBeDisabled()
    release()
  })
})

describe('StrictInterviewFlow, an interview that has ended', () => {
  beforeEach(() => {
    setFocus(true)
    document.hasFocus = () => focused
  })

  it('shows the ended screen straight away for a conduct ending, without asking for the camera or full screen', () => {
    setup({ endedStatus: 'ENDED_CONDUCT', subtitle: 'Acme · Sales Executive' })

    expect(screen.getByTestId('ended-screen')).toBeInTheDocument()
    expect(screen.getByText('Your interview has ended')).toBeInTheDocument()
    expect(screen.getByText('Acme · Sales Executive')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Start the interview' })).not.toBeInTheDocument()
    expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled()
  })

  it('shows the stopped wording for an interview the candidate stopped', () => {
    setup({ endedStatus: 'STOPPED' })

    expect(screen.getByText('You stopped the interview')).toBeInTheDocument()
  })

  it('shows the ended screen, and records nothing, when starting finds the interview already ended', async () => {
    const camera = fakeCamera()
    navigator.mediaDevices.getUserMedia = vi.fn(async () => camera)
    const startInterview = vi.fn(async () => ENDED('TOO_LONG_AWAY'))
    setup({ startInterview, resuming: true })

    await continueInterview()

    expect(await screen.findByTestId('ended-screen')).toBeInTheDocument()
    expect(camera.getTracks().every((track) => track.stop.mock.calls.length >= 1)).toBe(true)
    expect(FakeMediaRecorder.instances).toHaveLength(0)
    expect(uploadRecording).not.toHaveBeenCalled()
  })

  it('ends when the answer that was sent comes back saying the interview ended', async () => {
    const sendAnswer = vi.fn(async () => ENDED('TOO_MANY_LEAVES'))
    const { completeUpload } = setup({ sendAnswer })
    await acceptAndStart()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByTestId('ended-screen')).toBeInTheDocument()
    expect(completeUpload).toHaveBeenCalledTimes(1)
  })

  it('never calls an ending cheating, failing or a violation', async () => {
    setup({ endedStatus: 'ENDED_CONDUCT' })

    expect(screen.getByTestId('ended-screen').textContent).not.toMatch(/cheat|fail|violat|suspicio|caught/i)
  })

  it('says the recording could not be sent, in the ended wording, and lets the candidate retry', async () => {
    uploadRecording.mockRejectedValueOnce({ response: { status: 422, data: { message: 'We did not receive your recording.' } } })
    setup({ sendAnswer: vi.fn(async () => ENDED('TOO_MANY_LEAVES')) })
    await acceptAndStart()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText(/Your interview has ended, but the recording/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry upload' }))

    expect(await screen.findByTestId('ended-screen')).toBeInTheDocument()
  })
})

describe('StrictInterviewFlow, coming back to a reloaded or reinstated interview', () => {
  it('tells someone who reloaded that coming back counts as leaving once', () => {
    setup({ resuming: true })

    expect(screen.getByText(/counts as leaving the screen once/)).toBeInTheDocument()
  })

  it('tells someone the employer reinstated that they carry on with the time they had left and fresh warnings', () => {
    setup({ resuming: true, reinstated: true })

    expect(screen.getByText(/The employer has let you carry on/)).toBeInTheDocument()
    expect(screen.getByText(/with the time you had left/)).toBeInTheDocument()
    expect(screen.queryByText(/counts as leaving the screen once/)).not.toBeInTheDocument()
  })
})
