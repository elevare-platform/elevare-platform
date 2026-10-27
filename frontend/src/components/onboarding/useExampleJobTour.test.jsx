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
import { EXAMPLE_JOB_STEPS, EXAMPLE_VIEW_DEFAULT } from './tourSteps'

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
      'Match score',
      'Add people to the interview list',
      'Upload CVs and score them',
      'The talent pool',
      'Upload up to 20 CVs at once',
      'Choose the job to score against',
      'Rank your pool against a job',
      'Scores arrive as CVs are read',
      'Interview list',
      'Send interviews',
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

    expect(setView).toHaveBeenCalledWith(EXAMPLE_VIEW_DEFAULT)
  })

  it('puts the page in the right state before each step, forwards and back', async () => {
    render()
    await waitForDelay()
    setView.mockClear()

    // From the interview button on to "Upload CVs": the Talent Pipeline tab, with the
    // person just added still on the list.
    act(() => stepsOf()[3].popover.onNextClick())
    expect(setView).toHaveBeenLastCalledWith({ ...EXAMPLE_VIEW_DEFAULT, tab: 'pipeline', listed: ['a1'] })
    expect(created[0].moveNext).toHaveBeenCalled()

    // Back from the cost step: the dialog must close and the interview list stay.
    act(() => stepsOf()[12].popover.onPrevClick())
    expect(setView).toHaveBeenLastCalledWith({
      ...EXAMPLE_VIEW_DEFAULT, tab: 'interviews', listed: ['a1', 'p1'],
    })
    expect(created[0].movePrevious).toHaveBeenCalled()
  })

  it('moves to the Talent Pool when the CV upload is introduced', async () => {
    render()
    await waitForDelay()

    act(() => stepsOf()[4].popover.onNextClick())

    expect(setView).toHaveBeenLastCalledWith({ ...EXAMPLE_VIEW_DEFAULT, page: 'pool', listed: ['a1'] })
  })

  it('opens the upload drawer, then picks the job to score against, then closes the drawer', async () => {
    render()
    await waitForDelay()

    act(() => stepsOf()[5].popover.onNextClick())
    expect(setView).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 'pool', drawer: true, poolJob: '' }),
    )

    act(() => stepsOf()[6].popover.onNextClick())
    expect(setView).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 'pool', drawer: true, poolJob: 'sales' }),
    )

    act(() => stepsOf()[7].popover.onNextClick())
    expect(setView).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 'pool', drawer: false, poolJob: 'sales' }),
    )
  })

  it('returns to the job with the people added so far still on the interview list', async () => {
    render()
    await waitForDelay()

    act(() => stepsOf()[8].popover.onNextClick())

    expect(setView).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 'job', tab: 'pipeline', listed: ['a1', 'p1'] }),
    )
  })

  it('opens the dialog for the cost step', async () => {
    render()
    await waitForDelay()

    act(() => stepsOf()[11].popover.onNextClick())

    expect(setView).toHaveBeenLastCalledWith(
      expect.objectContaining({ tab: 'interviews', dialog: true, listed: ['a1', 'p1'] }),
    )
  })

  it('says the real cost when the account is charged, and a general line when not', async () => {
    const { unmount } = render('Each interview costs 8 credits, taken when you first send it.')
    await waitForDelay()
    expect(stepsOf()[12].popover.description).toContain('costs 8 credits')
    unmount()

    created.length = 0
    render()
    await waitForDelay()
    expect(stepsOf()[12].popover.description).toContain('uses credits')
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

    expect(created[0].config.progressText).toBe('Example: {{current}} of {{total}}')
  })
})
