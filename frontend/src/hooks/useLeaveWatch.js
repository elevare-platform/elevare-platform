import { useEffect, useRef } from 'react'
import { LEAVE_DELAY_MS, awayCause } from '@/lib/strictConduct'

/**
 * Tells the strict interview when the candidate leaves the screen and when they are back.
 *
 * A leave is the page hidden, the window out of focus, or full screen exited (see awayCause); all
 * at once is one leave. `onLeft(cause)` is called only once the candidate has been away for
 * `delayMs` (a second), so a notification or a blip never reaches the server, and `onReturned()`
 * when they are back, but only for a leave that was reported. While `active` is false nothing is
 * watched. The callbacks may change on every render.
 */
export function useLeaveWatch({ active, onLeft, onReturned, delayMs = LEAVE_DELAY_MS }) {
  const callbacks = useRef({ onLeft, onReturned })
  useEffect(() => {
    callbacks.current = { onLeft, onReturned }
  })

  useEffect(() => {
    if (!active) return undefined
    let timer = null
    let reported = false

    const check = () => {
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
      document.removeEventListener('visibilitychange', check)
      document.removeEventListener('fullscreenchange', check)
      window.removeEventListener('blur', check)
      window.removeEventListener('focus', check)
    }
  }, [active, delayMs])
}
