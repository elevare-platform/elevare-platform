import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

let mockOnboarding
vi.mock('@/hooks/useOnboarding', () => ({ useOnboarding: () => mockOnboarding }))

// driver.js draws on the real page; here it is a stand-in that keeps the settings it was
// given so the tests can press its buttons.
const created = []
vi.mock('driver.js', () => ({
  driver: vi.fn((config) => {
    const instance = {
      config,
      lastStep: false,
      drive: vi.fn(),
      destroy: vi.fn(),
      isLastStep: () => instance.lastStep,
    }
    created.push(instance)
    return instance
  }),
}))

import { useDashboardTour } from './useDashboardTour'

function addAnchors(...targets) {
  for (const target of targets) {
    const el = document.createElement('div')
    el.setAttribute('data-tour', target)
    document.body.appendChild(el)
  }
}

function setOnboarding(overrides = {}) {
  mockOnboarding = { loaded: true, tourStatus: 'PENDING', finishTour: vi.fn(), ...overrides }
}

const render = (autoStart = true) => renderHook(() => useDashboardTour({ autoStart }))
const waitForDelay = () => act(() => vi.advanceTimersByTimeAsync(1000))

describe('useDashboardTour', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    created.length = 0
    document.body.innerHTML = ''
    addAnchors('post-job', 'recent-jobs', 'tab-talent-pipeline')
    setOnboarding()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts by itself for someone who has not seen it', async () => {
    render()
    await waitForDelay()

    expect(created).toHaveLength(1)
    expect(created[0].drive).toHaveBeenCalledTimes(1)
  })

  it('leaves out steps whose element is not on the page', async () => {
    render()
    await waitForDelay()

    const titles = created[0].config.steps.map((s) => s.popover.title)
    expect(titles).toEqual(['Post a job', 'Your jobs and applicants', 'Talent pool'])
  })

  it.each([
    ['has finished it', { tourStatus: 'COMPLETED' }],
    ['has skipped it', { tourStatus: 'SKIPPED' }],
    ['could not be reached', { loaded: false, tourStatus: null }],
  ])('does not start when the server %s', async (_label, state) => {
    setOnboarding(state)
    render()
    await waitForDelay()

    expect(created).toHaveLength(0)
  })

  it('waits until the page says it is ready', async () => {
    const { rerender } = renderHook(({ ready }) => useDashboardTour({ autoStart: ready }), {
      initialProps: { ready: false },
    })
    await waitForDelay()
    expect(created).toHaveLength(0)

    rerender({ ready: true })
    await waitForDelay()
    expect(created).toHaveLength(1)
  })

  it('starts by itself only once', async () => {
    const { rerender } = render()
    await waitForDelay()
    rerender()
    await waitForDelay()

    expect(created).toHaveLength(1)
  })

  it('records completed when closed on the last step', async () => {
    render()
    await waitForDelay()
    created[0].lastStep = true

    act(() => created[0].config.onDestroyStarted())

    expect(created[0].destroy).toHaveBeenCalled()
    expect(mockOnboarding.finishTour).toHaveBeenCalledWith('COMPLETED')
  })

  it('records skipped when closed before the end', async () => {
    render()
    await waitForDelay()

    act(() => created[0].config.onDestroyStarted())

    expect(mockOnboarding.finishTour).toHaveBeenCalledWith('SKIPPED')
  })

  it('has a Skip tour button that records skipped', async () => {
    render()
    await waitForDelay()
    const description = document.createElement('div')
    document.body.appendChild(description)
    created[0].config.onPopoverRender({ description })

    const skip = description.nextElementSibling
    expect(skip).toHaveTextContent('Skip tour')
    act(() => skip.click())

    expect(mockOnboarding.finishTour).toHaveBeenCalledWith('SKIPPED')
  })

  it('does not end the tour when the dimmed page is clicked', async () => {
    render()
    await waitForDelay()

    expect(typeof created[0].config.overlayClickBehavior).toBe('function')
    created[0].config.overlayClickBehavior()
    expect(mockOnboarding.finishTour).not.toHaveBeenCalled()
  })

  it('can be run again on request, without recording it a second time', () => {
    setOnboarding({ tourStatus: 'COMPLETED' })
    const { result } = render(false)

    act(() => { result.current.start() })
    expect(created).toHaveLength(1)

    act(() => created[0].config.onDestroyStarted())
    expect(mockOnboarding.finishTour).not.toHaveBeenCalled()
  })

  it('records nothing when the person leaves the page halfway', async () => {
    const { unmount } = render()
    await waitForDelay()

    unmount()

    expect(created[0].destroy).toHaveBeenCalled()
    expect(mockOnboarding.finishTour).not.toHaveBeenCalled()
  })

  it('does not start when none of the pointed-at elements are on the page', () => {
    document.body.innerHTML = ''
    const { result } = render(false)

    let started
    act(() => { started = result.current.start() })

    expect(started).toBe(false)
    expect(created).toHaveLength(0)
  })
})
