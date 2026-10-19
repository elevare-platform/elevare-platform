import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

let mockOnboarding
vi.mock('@/hooks/useOnboarding', () => ({ useOnboarding: () => mockOnboarding }))

const created = []
vi.mock('driver.js', () => ({
  driver: vi.fn((config) => {
    const instance = {
      config,
      lastStep: false,
      drive: vi.fn(),
      destroy: vi.fn(),
      moveNext: vi.fn(),
      movePrevious: vi.fn(),
      isLastStep: () => instance.lastStep,
    }
    created.push(instance)
    return instance
  }),
}))

import { useExampleJobTour } from './useExampleJobTour'
import { EXAMPLE_JOB_STEPS } from './tourSteps'

const setView = vi.fn()
const onClosed = vi.fn()
const waitForDelay = () => act(() => vi.advanceTimersByTimeAsync(1000))
const render = (costText) => renderHook(() => useExampleJobTour({ setView, costText, onClosed, autoStart: true }))
const stepsOf = () => created[0].config.steps

describe('useExampleJobTour', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    created.length = 0
    document.body.innerHTML = ''
    mockOnboarding = { loaded: true, tourStatus: 'PENDING', finishTour: vi.fn() }
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('walks the example job in the order a new employer meets things', async () => {
    render()
    await waitForDelay()

    expect(stepsOf().map((s) => s.popover.title)).toEqual([
      'An example job',
      'Applicants',
      'AI score',
      'Upload CVs and score them',
      'Scores arrive as CVs are read',
      'Interview list',
      'Send AI interviews',
      'What an interview costs',
    ])
  })

  it('starts by itself even when the person has already seen the first part', async () => {
    mockOnboarding = { loaded: false, tourStatus: null, finishTour: vi.fn() }
    render()
    await waitForDelay()

    expect(created).toHaveLength(1)
  })

  it('does not wait for the elements, because they appear after the page changes', async () => {
    render()
    await waitForDelay()

    expect(created[0].config.waitForElement).toBeGreaterThan(0)
    expect(stepsOf()).toHaveLength(EXAMPLE_JOB_STEPS.length)
  })

  it('shows the first state of the page as it starts', async () => {
    render()
    await waitForDelay()

    expect(setView).toHaveBeenCalledWith({ tab: 'applicants', reasoning: false, dialog: false })
  })

  it('puts the page in the right state before each step, forwards and back', async () => {
    render()
    await waitForDelay()
    setView.mockClear()

    // From "AI score" on to "Upload CVs": the Talent Pipeline tab must be showing.
    act(() => stepsOf()[2].popover.onNextClick())
    expect(setView).toHaveBeenLastCalledWith({ tab: 'pipeline', reasoning: false, dialog: false })
    expect(created[0].moveNext).toHaveBeenCalled()

    // Back from the cost step: the dialog must close and the interview list stay.
    act(() => stepsOf()[7].popover.onPrevClick())
    expect(setView).toHaveBeenLastCalledWith({ tab: 'interviews', reasoning: false, dialog: false })
    expect(created[0].movePrevious).toHaveBeenCalled()
  })

  it('opens the dialog for the cost step', async () => {
    render()
    await waitForDelay()

    act(() => stepsOf()[6].popover.onNextClick())

    expect(setView).toHaveBeenLastCalledWith({ tab: 'interviews', reasoning: false, dialog: true })
  })

  it('says the real cost when the account is charged, and a general line when not', async () => {
    const { unmount } = render('Each AI interview costs 8 credits, taken when you first send it.')
    await waitForDelay()
    expect(stepsOf()[7].popover.description).toContain('costs 8 credits')
    unmount()

    created.length = 0
    render()
    await waitForDelay()
    expect(stepsOf()[7].popover.description).toContain('uses credits')
  })

  it('completes the tour and goes back when the last step is finished', async () => {
    render()
    await waitForDelay()
    created[0].lastStep = true

    act(() => created[0].config.onDestroyStarted())

    expect(mockOnboarding.finishTour).toHaveBeenCalledWith('COMPLETED')
    expect(onClosed).toHaveBeenCalledWith('COMPLETED')
  })

  it('counts leaving early as skipped, and still goes back', async () => {
    render()
    await waitForDelay()

    act(() => created[0].config.onDestroyStarted())

    expect(mockOnboarding.finishTour).toHaveBeenCalledWith('SKIPPED')
    expect(onClosed).toHaveBeenCalledWith('SKIPPED')
  })

  it('leaves the button label alone so the last step says Done', async () => {
    render()
    await waitForDelay()

    for (const step of stepsOf()) {
      expect('nextBtnText' in step.popover).toBe(false)
    }
  })

  it('shows which part of the tour this is', async () => {
    render()
    await waitForDelay()

    expect(created[0].config.progressText).toBe('Example job: {{current}} of {{total}}')
  })
})
