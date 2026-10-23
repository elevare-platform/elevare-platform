import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { CALM_MS } from '@/lib/strictConduct'
import { useLeaveWatch } from './useLeaveWatch'

// The page state the hook reads, set by the tests.
let page
function setPage(over) {
  page = { visibilityState: 'visible', focused: true, fullscreen: {}, ...over }
}

function fire(target, name) {
  act(() => { target.dispatchEvent(new Event(name)) })
}

beforeEach(() => {
  vi.useFakeTimers()
  setPage({})
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => page.visibilityState })
  Object.defineProperty(document, 'fullscreenElement', { configurable: true, get: () => page.fullscreen })
  document.hasFocus = () => page.focused
})

afterEach(() => {
  vi.useRealTimers()
})

function watch(props = {}) {
  const onLeft = vi.fn()
  const onReturned = vi.fn()
  const view = renderHook((current) => useLeaveWatch({ active: true, onLeft, onReturned, ...current }), {
    initialProps: props,
  })
  // The watch counts once the screen has been calm for a moment; a screen that starts calm gets
  // there before anything a test does next.
  if (page.visibilityState === 'visible' && page.focused && page.fullscreen) {
    act(() => { vi.advanceTimersByTime(CALM_MS + 100) })
  }
  return { onLeft, onReturned, ...view }
}

describe('useLeaveWatch', () => {
  it('reports nothing while the candidate stays on the page', () => {
    const { onLeft, onReturned } = watch()

    act(() => { vi.advanceTimersByTime(10_000) })

    expect(onLeft).not.toHaveBeenCalled()
    expect(onReturned).not.toHaveBeenCalled()
  })

  it('reports a leave only after a second away, with its cause', () => {
    const { onLeft } = watch()

    setPage({ visibilityState: 'hidden' })
    fire(document, 'visibilitychange')
    act(() => { vi.advanceTimersByTime(999) })
    expect(onLeft).not.toHaveBeenCalled()
    act(() => { vi.advanceTimersByTime(2) })

    expect(onLeft).toHaveBeenCalledTimes(1)
    expect(onLeft).toHaveBeenCalledWith('HIDDEN')
  })

  it('never reports a blip shorter than a second, nor its return', () => {
    const { onLeft, onReturned } = watch()

    setPage({ focused: false })
    fire(window, 'blur')
    act(() => { vi.advanceTimersByTime(400) })
    setPage({ focused: true })
    fire(window, 'focus')
    act(() => { vi.advanceTimersByTime(5_000) })

    expect(onLeft).not.toHaveBeenCalled()
    expect(onReturned).not.toHaveBeenCalled()
  })

  it('reports the return of a leave it reported', () => {
    const { onLeft, onReturned } = watch()
    setPage({ focused: false })
    fire(window, 'blur')
    act(() => { vi.advanceTimersByTime(1500) })

    setPage({ focused: true })
    fire(window, 'focus')

    expect(onLeft).toHaveBeenCalledWith('BLUR')
    expect(onReturned).toHaveBeenCalledTimes(1)
  })

  it('reports leaving full screen as a leave', () => {
    const { onLeft } = watch()

    setPage({ fullscreen: null })
    fire(document, 'fullscreenchange')
    act(() => { vi.advanceTimersByTime(1100) })

    expect(onLeft).toHaveBeenCalledWith('FULLSCREEN')
  })

  it('counts several causes at once as one leave', () => {
    const { onLeft, onReturned } = watch()

    // Switching tab hides the page, drops focus and, in some browsers, leaves full screen.
    setPage({ visibilityState: 'hidden', focused: false, fullscreen: null })
    fire(document, 'visibilitychange')
    fire(window, 'blur')
    fire(document, 'fullscreenchange')
    act(() => { vi.advanceTimersByTime(3000) })
    expect(onLeft).toHaveBeenCalledTimes(1)

    // Coming back takes three events; only when all are clear is the candidate back.
    setPage({ visibilityState: 'visible', focused: true, fullscreen: null })
    fire(document, 'visibilitychange')
    fire(window, 'focus')
    expect(onReturned).not.toHaveBeenCalled()
    setPage({ fullscreen: {} })
    fire(document, 'fullscreenchange')

    expect(onReturned).toHaveBeenCalledTimes(1)
  })

  it('reports the next leave separately once the candidate is back', () => {
    const { onLeft, onReturned } = watch()
    for (let round = 0; round < 3; round += 1) {
      setPage({ focused: false })
      fire(window, 'blur')
      act(() => { vi.advanceTimersByTime(1200) })
      setPage({ focused: true })
      fire(window, 'focus')
    }

    expect(onLeft).toHaveBeenCalledTimes(3)
    expect(onReturned).toHaveBeenCalledTimes(3)
  })

  it('counts nothing until the screen has settled once, so a pop-up at the start is not a leave', () => {
    // The interview starts with the window not yet settled (a browser pop-up has the focus).
    setPage({ focused: false })
    const { onLeft, onReturned } = watch()

    act(() => { vi.advanceTimersByTime(5000) })
    expect(onLeft).not.toHaveBeenCalled()

    // The pop-up is dismissed and the screen settles: still nothing was a leave.
    setPage({ focused: true })
    fire(window, 'focus')
    act(() => { vi.advanceTimersByTime(5000) })

    expect(onLeft).not.toHaveBeenCalled()
    expect(onReturned).not.toHaveBeenCalled()
  })

  it('arms only after the screen has been calm for a moment, so a pop-up just after full screen is not a leave', () => {
    const onLeft = vi.fn()
    renderHook(() => useLeaveWatch({ active: true, onLeft, onReturned: vi.fn() }))

    // Calm at the start, then a pop-up takes the focus 300 ms later and gives it back at 4 s.
    act(() => { vi.advanceTimersByTime(300) })
    setPage({ focused: false })
    fire(window, 'blur')
    act(() => { vi.advanceTimersByTime(3700) })
    setPage({ focused: true })
    fire(window, 'focus')
    act(() => { vi.advanceTimersByTime(3000) })

    expect(onLeft).not.toHaveBeenCalled()
  })

  it('counts a leave normally once the screen has settled', () => {
    setPage({ focused: false })
    const { onLeft } = watch()
    setPage({ focused: true })
    fire(window, 'focus')
    act(() => { vi.advanceTimersByTime(CALM_MS + 100) })

    setPage({ focused: false })
    fire(window, 'blur')
    act(() => { vi.advanceTimersByTime(1200) })

    expect(onLeft).toHaveBeenCalledWith('BLUR')
  })

  it('counts a candidate who never settles, from the settling time on', () => {
    setPage({ focused: false })
    const { onLeft } = watch({ settleMs: 15_000 })

    act(() => { vi.advanceTimersByTime(14_000) })
    expect(onLeft).not.toHaveBeenCalled()
    act(() => { vi.advanceTimersByTime(2500) })

    expect(onLeft).toHaveBeenCalledWith('BLUR')
  })

  it('reports a candidate who is already away when watching starts, once the settling time has passed', () => {
    setPage({ focused: false })

    const { onLeft } = watch()
    act(() => { vi.advanceTimersByTime(17_000) })

    expect(onLeft).toHaveBeenCalledWith('BLUR')
  })

  it('does not watch while it is not active, and stops when it becomes inactive', () => {
    const { onLeft, rerender } = watch({ active: false })
    setPage({ focused: false })
    fire(window, 'blur')
    act(() => { vi.advanceTimersByTime(30_000) })
    expect(onLeft).not.toHaveBeenCalled()

    // Watching starts with the window away: counted once the settling time is up.
    rerender({ active: true })
    act(() => { vi.advanceTimersByTime(17_000) })
    expect(onLeft).toHaveBeenCalledTimes(1)

    setPage({ focused: true })
    rerender({ active: false })
    setPage({ focused: false })
    fire(window, 'blur')
    act(() => { vi.advanceTimersByTime(30_000) })
    expect(onLeft).toHaveBeenCalledTimes(1)
  })

  it('calls the latest callbacks, not the ones from when it started watching', () => {
    const first = vi.fn()
    const second = vi.fn()
    const { rerender } = renderHook((props) => useLeaveWatch({ active: true, ...props }), {
      initialProps: { onLeft: first },
    })

    rerender({ onLeft: second })
    act(() => { vi.advanceTimersByTime(CALM_MS + 100) })
    setPage({ focused: false })
    fire(window, 'blur')
    act(() => { vi.advanceTimersByTime(1200) })

    expect(first).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledWith('BLUR')
  })

  it('stops its timer and listeners when it is removed', () => {
    const { onLeft, unmount } = watch()
    setPage({ focused: false })
    fire(window, 'blur')

    unmount()
    act(() => { vi.advanceTimersByTime(5000) })

    expect(onLeft).not.toHaveBeenCalled()
  })
})
