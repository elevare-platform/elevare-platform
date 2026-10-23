import { useEffect, useRef } from 'react'
import { CALM_MS, LEAVE_DELAY_MS, SETTLE_MS, awayCause } from '@/lib/strictConduct'

/**
 * Tells the strict interview when the candidate leaves the screen and when they are back.
 *
 * A leave is the page hidden, the window out of focus, or full screen exited (see awayCause); all
 * at once is one leave. `onLeft(cause)` is called only once the candidate has been away for
 * `delayMs` (a second), so a notification or a blip never reaches the server, and `onReturned()`
 * when they are back, but only for a leave that was reported. While `active` is false nothing is
 * watched. The callbacks may change on every render.
 *
 * The watch is ARMED once the screen has been calm (visible, in focus, full screen) for `calmMs`
 * in a row after it starts, or after `settleMs` whichever comes first. Until then nothing counts:
 * the start of the interview has its own transitions (full screen taking effect, a browser
 * pop-up arriving a moment later) and none of them is the candidate leaving. A candidate who is
 * never calm is counted from `settleMs` on.
 */
export function useLeaveWatch({
  active,
  onLeft,
  onReturned,
  delayMs = LEAVE_DELAY_MS,
  calmMs = CALM_MS,
  settleMs = SETTLE_MS,
}) {
  const callbacks = useRef({ onLeft, onReturned })
  useEffect(() => {
    callbacks.current = { onLeft, onReturned }
  })

  useEffect(() => {
    if (!active) return undefined
    const startedAt = Date.now()
    let timer = null
    let settleTimer = null
    let calmTimer = null
    let reported = false
    let armed = false

    const check = () => {
      if (!armed) {
        if (Date.now() - startedAt >= settleMs) {
          armed = true
        } else {
          // Not armed yet. Calm for long enough arms it; anything else starts the wait again.
          if (awayCause(document)) {
            if (calmTimer) { clearTimeout(calmTimer); calmTimer = null }
          } else if (!calmTimer) {
            calmTimer = setTimeout(() => {
              calmTimer = null
              if (!awayCause(document)) armed = true
              check()
            }, calmMs)
          }
          // A candidate who is never calm is counted from `settleMs` on.
          if (!settleTimer) settleTimer = setTimeout(() => { settleTimer = null; check() }, settleMs - (Date.now() - startedAt) + 5)
          return
        }
      }
      if (awayCause(document)) {
        if (timer || reported) return
        timer = setTimeout(() => {
          timer = null
          const cause = awayCause(document)
          if (cause) {
            reported = true
            callbacks.current.onLeft?.(cause)
          }
        }, delayMs)
      } else {
        if (timer) {
          clearTimeout(timer)
          timer = null
        }
        if (reported) {
          reported = false
          callbacks.current.onReturned?.()
        }
      }
    }

    document.addEventListener('visibilitychange', check)
    document.addEventListener('fullscreenchange', check)
    window.addEventListener('blur', check)
    window.addEventListener('focus', check)
    check()
    return () => {
      if (timer) clearTimeout(timer)
      if (settleTimer) clearTimeout(settleTimer)
      if (calmTimer) clearTimeout(calmTimer)
      document.removeEventListener('visibilitychange', check)
      document.removeEventListener('fullscreenchange', check)
      window.removeEventListener('blur', check)
      window.removeEventListener('focus', check)
    }
  }, [active, delayMs, calmMs, settleMs])
}
