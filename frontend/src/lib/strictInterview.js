// Pure helpers for the strict AI interview screen (docs/08_DECISIONS.md, "The new strict,
// text-only AI interview"): can this device take it, which keys are switched off, how a clock
// reads, which audio format to record. No React and no network here, so each can be tested.

// What the screen needs from the browser, read in one place so a test can hand in any browser.
export function browserEnvironment() {
  const nav = typeof navigator === 'undefined' ? {} : navigator
  const doc = typeof document === 'undefined' ? null : document
  const recorder = typeof MediaRecorder === 'undefined' ? null : MediaRecorder
  return {
    userAgent: nav.userAgent || '',
    brands: nav.userAgentData?.brands?.map((entry) => entry.brand) ?? null,
    mobile: nav.userAgentData?.mobile ?? null,
    hasGetUserMedia: Boolean(nav.mediaDevices?.getUserMedia),
    hasMediaRecorder: Boolean(recorder),
    canRecordWebm: Boolean(recorder?.isTypeSupported?.('video/webm')),
    hasFullscreen: Boolean(doc?.documentElement?.requestFullscreen),
    // True only when the browser reports more than one screen joined into the desktop. Undefined
    // when the browser cannot tell, which is allowed through: it can only be refused when known.
    extendedDesktop: typeof window !== 'undefined' ? window.screen?.isExtended ?? null : null,
  }
}

function isChromeOrEdge({ userAgent, brands }) {
  if (brands && brands.length > 0) {
    return brands.some((brand) => brand === 'Google Chrome' || brand === 'Microsoft Edge')
  }
  return /(Chrome|Edg)\//.test(userAgent) && !/(OPR|Firefox|SamsungBrowser)\//.test(userAgent)
}

function isPhoneOrTablet({ userAgent, mobile }) {
  return mobile === true || /Android|iPhone|iPad|iPod|Mobile|Tablet/i.test(userAgent)
}

/**
 * Whether this device can take the strict interview. Returns `{ ok, problems }`, where each
 * problem has an id and a sentence for the candidate. The order is the order to show them in:
 * the kind of device first, because the rest is moot on a phone.
 */
export function checkDevice(env = browserEnvironment()) {
  const problems = []
  if (isPhoneOrTablet(env)) {
    problems.push({
      id: 'device',
      message: 'This interview cannot be taken on a phone or a tablet. Please open the link on a laptop or desktop computer.',
    })
  }
  if (!isChromeOrEdge(env)) {
    problems.push({
      id: 'browser',
      message: 'Please open this link in the latest Chrome or Edge. Other browsers cannot run this interview.',
    })
  }
  if (!env.hasGetUserMedia || !env.hasMediaRecorder || !env.canRecordWebm) {
    problems.push({
      id: 'recording',
      message: "This browser can't record the interview with your camera and microphone. Please use the latest Chrome or Edge.",
    })
  }
  if (!env.hasFullscreen) {
    problems.push({
      id: 'fullscreen',
      message: "This browser can't show the interview in full screen, which it needs. Please use the latest Chrome or Edge.",
    })
  }
  if (env.extendedDesktop === true) {
    problems.push({
      id: 'second-screen',
      message: 'A second screen is connected. Please disconnect it, then reload this page.',
    })
  }
  return { ok: problems.length === 0, problems }
}

/** The audio format to record each answer in, or null when the browser cannot record audio. */
export function pickAnswerMimeType(recorder = typeof MediaRecorder === 'undefined' ? null : MediaRecorder) {
  if (!recorder) return null
  const candidates = ['audio/webm;codecs=opus', 'audio/webm']
  return candidates.find((type) => recorder.isTypeSupported?.(type)) ?? null
}

/** The format to record the whole interview in (the server stores and plays WebM only). */
export function pickInterviewMimeType(recorder = typeof MediaRecorder === 'undefined' ? null : MediaRecorder) {
  if (!recorder) return null
  const candidates = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm']
  return candidates.find((type) => recorder.isTypeSupported?.(type)) ?? null
}

/**
 * Whether a key press is switched off during the interview. Nothing in the interview is typed,
 * so every shortcut (anything with Ctrl, Alt or the Windows or Command key), every function key,
 * Print Screen and the menu key are blocked. Plain Tab, Enter and Space stay, so the Next button
 * can still be reached from the keyboard.
 */
export function shouldBlockKey(event) {
  if (event.ctrlKey || event.altKey || event.metaKey) return true
  if (/^F([1-9]|1[0-9]|2[0-4])$/.test(event.key)) return true
  return event.key === 'PrintScreen' || event.key === 'ContextMenu' || event.key === 'Meta' || event.key === 'OS'
}

/** Seconds as m:ss, never negative. */
export function formatClock(totalSeconds) {
  const seconds = Math.max(0, Math.round(totalSeconds))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

/** The label above a question: "Question 2 of 5", or "Follow-up to question 2". */
export function turnLabel(turn, totalQuestions) {
  if (!turn) return ''
  return turn.kind === 'FOLLOW_UP'
    ? `Follow-up to question ${turn.number}`
    : `Question ${turn.number} of ${totalQuestions}`
}
