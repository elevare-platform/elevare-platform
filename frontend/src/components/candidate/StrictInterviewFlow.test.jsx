import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/interviewUpload', async (importOriginal) => ({
  ...(await importOriginal()),
  uploadRecording: vi.fn(async () => {}),
}))
vi.mock('@/lib/strictInterview', async (importOriginal) => ({
  ...(await importOriginal()),
  checkDevice: vi.fn(() => ({ ok: true, problems: [] })),
}))

import { uploadRecording } from '@/lib/interviewUpload'
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
    { kind: 'audio', stop: vi.fn() },
    { kind: 'video', stop: vi.fn() },
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

async function acceptAndStart() {
  fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Start the interview' }))
  await screen.findByTestId('question-text')
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

  it('does not tell the candidate that leaving the page is noted, since nothing notes it yet', () => {
    setup()

    expect(screen.queryByText(/is noted and shown to the employer/)).not.toBeInTheDocument()
  })

  it('will not start until the rules are accepted', () => {
    setup()
    const start = screen.getByRole('button', { name: 'Start the interview' })

    expect(start).toBeDisabled()
    fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules/ }))
    expect(start).toBeEnabled()
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

    expect(screen.getByRole('alert')).toHaveTextContent('latest Chrome or Edge')
    expect(screen.getByRole('alert')).toHaveTextContent('second screen is connected')
    expect(screen.getByRole('button', { name: 'Start the interview' })).toBeDisabled()
  })

  it('welcomes a returning candidate back without asking for the rules again', () => {
    setup({ resuming: true })

    expect(screen.getByText(/You started this interview earlier/)).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
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

    fireEvent.click(screen.getByRole('button', { name: 'Continue the interview' }))
    await screen.findByTestId('question-text')

    expect(startInterview).toHaveBeenCalled()
  })

  it('says so when full screen is refused, and never opens the camera', async () => {
    document.documentElement.requestFullscreen = vi.fn(async () => { throw new Error('denied') })
    const { startInterview } = setup()

    fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Start the interview' }))

    expect(await screen.findByText(/needs full screen/)).toBeInTheDocument()
    expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled()
    expect(startInterview).not.toHaveBeenCalled()
  })

  it('says so when the camera is refused, and gives the screen back', async () => {
    navigator.mediaDevices.getUserMedia = vi.fn(async () => {
      throw Object.assign(new Error('no'), { name: 'NotAllowedError' })
    })
    const { startInterview } = setup()

    fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Start the interview' }))

    expect(await screen.findByText('Camera and microphone access is required for the interview.')).toBeInTheDocument()
    expect(startInterview).not.toHaveBeenCalled()
    expect(document.exitFullscreen).toHaveBeenCalled()
  })

  it("shows the server's own message when it refuses to start, and stops the camera", async () => {
    const camera = fakeCamera()
    navigator.mediaDevices.getUserMedia = vi.fn(async () => camera)
    const startInterview = vi.fn(async () => {
      throw { response: { data: { message: 'The questions for this interview are not ready. Please contact your recruiter.' } } }
    })
    setup({ startInterview })

    fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules/ }))
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

    fireEvent.click(screen.getByRole('button', { name: 'Continue the interview' }))

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
