import { useEffect } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

let mockUser = { id: 'u1', role: 'EMPLOYER' }
vi.mock('@/context/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

import api from '@/lib/api'
import { OnboardingProvider } from './OnboardingContext'
import { useOnboarding, useReportStep } from '@/hooks/useOnboarding'

const FRESH = { tour_status: 'PENDING', completed_steps: [], checklist_dismissed: false }

let latest
function Probe() {
  const onboarding = useOnboarding()
  useEffect(() => {
    latest = onboarding
  })
  return (
    <p data-testid="state">
      {String(onboarding.loaded)}|{onboarding.tourStatus}|{onboarding.completedSteps.join(',')}
    </p>
  )
}

function ReportsStep({ step }) {
  useReportStep(step)
  return null
}

const renderProvider = (children = <Probe />) =>
  render(<OnboardingProvider>{children}</OnboardingProvider>)

describe('OnboardingProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUser = { id: 'u1', role: 'EMPLOYER' }
  })

  it('loads the employer\'s progress from the server', async () => {
    api.get.mockResolvedValueOnce({
      data: { tour_status: 'SKIPPED', completed_steps: ['credits'], checklist_dismissed: true },
    })
    renderProvider()

    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('true|SKIPPED|credits'))
    expect(api.get).toHaveBeenCalledWith('/api/v1/onboarding/me')
    expect(latest.checklistDismissed).toBe(true)
  })

  it('loads a candidate\'s tour progress too', async () => {
    mockUser = { id: 'c1', role: 'CANDIDATE' }
    api.get.mockResolvedValueOnce({ data: FRESH })
    renderProvider()

    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('true|PENDING'))
    expect(api.get).toHaveBeenCalledWith('/api/v1/onboarding/me')
  })

  it('records how a candidate\'s tour ended, but never reports checklist steps for one', async () => {
    mockUser = { id: 'c1', role: 'CANDIDATE' }
    api.get.mockResolvedValueOnce({ data: FRESH })
    api.post.mockResolvedValue({ data: { ...FRESH, tour_status: 'SKIPPED' } })
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('true'))

    act(() => latest.markStep('credits'))
    act(() => latest.dismissChecklist())
    act(() => latest.finishTour('SKIPPED'))

    expect(api.post).toHaveBeenCalledTimes(1)
    expect(api.post).toHaveBeenCalledWith('/api/v1/onboarding/me/tour', { outcome: 'SKIPPED' })
  })

  it('does not ask for an admin or a signed-out visitor', async () => {
    mockUser = { id: 'a1', role: 'ADMIN' }
    renderProvider()

    expect(api.get).not.toHaveBeenCalled()
    expect(screen.getByTestId('state')).toHaveTextContent('false')
  })

  it('stays not loaded when the server cannot be reached, so the tour never starts on a guess', async () => {
    api.get.mockRejectedValueOnce(new Error('network'))
    renderProvider()

    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(latest.loaded).toBe(false)
    expect(latest.tourStatus).toBeNull()
  })

  it('reports a step once however many times it is asked', async () => {
    api.get.mockResolvedValueOnce({ data: FRESH })
    api.post.mockResolvedValue({ data: { ...FRESH, completed_steps: ['talent_pool'] } })
    renderProvider(<><Probe /><ReportsStep step="talent_pool" /><ReportsStep step="talent_pool" /></>)

    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('talent_pool'))
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(api.post).toHaveBeenCalledWith('/api/v1/onboarding/me/steps', { step: 'talent_pool' })
  })

  it('does not break the page when saving a step fails, and tries again next time', async () => {
    api.get.mockResolvedValueOnce({ data: FRESH })
    api.post.mockRejectedValueOnce(new Error('network')).mockResolvedValue({ data: FRESH })
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('true'))

    await act(async () => { latest.markStep('credits') })
    await act(async () => { latest.markStep('credits') })

    expect(api.post).toHaveBeenCalledTimes(2)
  })

  it('never shows one person\'s progress to the next person who logs in', async () => {
    api.get.mockResolvedValueOnce({
      data: { tour_status: 'COMPLETED', completed_steps: ['credits'], checklist_dismissed: true },
    })
    const view = renderProvider()
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('true|COMPLETED'))

    // A different employer logs in; their answer has not arrived yet.
    api.get.mockReturnValueOnce(new Promise(() => {}))
    mockUser = { id: 'u2', role: 'EMPLOYER' }
    view.rerender(<OnboardingProvider><Probe /></OnboardingProvider>)

    expect(screen.getByTestId('state')).toHaveTextContent('false')
    expect(latest.checklistDismissed).toBe(false)
  })

  it('keeps a step reported while the first answer was still on its way', async () => {
    let answer
    api.get.mockReturnValueOnce(new Promise((resolve) => { answer = resolve }))
    api.post.mockResolvedValue({ data: { ...FRESH, completed_steps: ['credits'] } })
    renderProvider(<><Probe /><ReportsStep step="credits" /></>)

    await waitFor(() => expect(api.post).toHaveBeenCalled())
    await act(async () => { answer({ data: FRESH }) })

    expect(screen.getByTestId('state')).toHaveTextContent('true|PENDING|credits')
  })

  it('records how the tour ended', async () => {
    api.get.mockResolvedValueOnce({ data: FRESH })
    api.post.mockResolvedValueOnce({ data: { ...FRESH, tour_status: 'COMPLETED' } })
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('true|PENDING'))

    act(() => latest.finishTour('COMPLETED'))

    expect(screen.getByTestId('state')).toHaveTextContent('COMPLETED')
    expect(api.post).toHaveBeenCalledWith('/api/v1/onboarding/me/tour', { outcome: 'COMPLETED' })
  })

  it('hides the checklist straight away and tells the server', async () => {
    api.get.mockResolvedValueOnce({ data: FRESH })
    api.post.mockResolvedValueOnce({ data: { ...FRESH, checklist_dismissed: true } })
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('true'))

    act(() => latest.dismissChecklist())

    expect(latest.checklistDismissed).toBe(true)
    expect(api.post).toHaveBeenCalledWith('/api/v1/onboarding/me/checklist/dismiss')
  })
})

describe('without a provider', () => {
  beforeEach(() => vi.clearAllMocks())

  it('lets a page report a step without doing anything', () => {
    expect(() => render(<ReportsStep step="credits" />)).not.toThrow()
    expect(api.post).not.toHaveBeenCalled()
  })
})
