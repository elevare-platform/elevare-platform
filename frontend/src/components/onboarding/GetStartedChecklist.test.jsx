import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

let mockOnboarding
vi.mock('@/hooks/useOnboarding', () => ({ useOnboarding: () => mockOnboarding }))

import GetStartedChecklist from './GetStartedChecklist'

const NEW_USER = { is_profile_complete: false, kyc_status: 'NOT_SUBMITTED' }
const NO_JOBS = { total_jobs: 0 }

function setup({ user = NEW_USER, stats = NO_JOBS, onboarding = {}, onShowTour } = {}) {
  mockOnboarding = {
    loaded: true,
    completedSteps: [],
    checklistDismissed: false,
    dismissChecklist: vi.fn(),
    ...onboarding,
  }
  render(
    <MemoryRouter>
      <GetStartedChecklist user={user} stats={stats} onShowTour={onShowTour} />
    </MemoryRouter>
  )
}

const row = (name) => screen.getByRole('link', { name: new RegExp(name) })

describe('GetStartedChecklist', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows all eight things to do for a brand new employer', () => {
    setup()

    expect(screen.getAllByRole('link')).toHaveLength(8)
    expect(screen.getByText('0 of 8 done')).toBeInTheDocument()
    expect(row('Complete your company profile')).toHaveTextContent('not done yet')
  })

  it('works out profile, verification and first job from the account, not from stored steps', () => {
    setup({
      user: { is_profile_complete: true, kyc_status: 'APPROVED' },
      stats: { total_jobs: 2 },
    })

    expect(row('Complete your company profile')).toHaveTextContent('(done)')
    expect(row('Verify your company')).toHaveTextContent('(done)')
    expect(row('Post your first job')).toHaveTextContent('(done)')
    expect(screen.getByText('3 of 8 done')).toBeInTheDocument()
  })

  it('says when verification is under review but does not count it as done', () => {
    setup({ user: { is_profile_complete: true, kyc_status: 'PENDING' } })

    expect(row('Verify your company')).toHaveTextContent('not done yet')
    expect(screen.getByText('Under review')).toBeInTheDocument()
  })

  it('ticks the steps the server says were done', () => {
    setup({ onboarding: { completedSteps: ['talent_pool', 'credits'] } })

    expect(row('Open the talent pool')).toHaveTextContent('(done)')
    expect(row('Check your credits')).toHaveTextContent('(done)')
    expect(row('Try candidate search')).toHaveTextContent('not done yet')
  })

  it('links each item to where it is done', () => {
    setup()

    expect(row('Post your first job')).toHaveAttribute('href', '/employer/jobs/new')
    expect(row('Check your credits')).toHaveAttribute('href', '/employer/billing')
    expect(row('Try the interview list')).toHaveAttribute('href', '/employer/jobs')
  })

  it('shows nothing until the server has answered, so it does not flash from not done to done', () => {
    setup({ onboarding: { loaded: false } })
    expect(screen.queryByText('Get started')).not.toBeInTheDocument()
  })

  it('shows nothing until the numbers are in', () => {
    setup({ stats: null })
    expect(screen.queryByText('Get started')).not.toBeInTheDocument()
  })

  it('stays hidden once dismissed', () => {
    setup({ onboarding: { checklistDismissed: true } })
    expect(screen.queryByText('Get started')).not.toBeInTheDocument()
  })

  it('goes away by itself when everything is done', () => {
    setup({
      user: { is_profile_complete: true, kyc_status: 'APPROVED' },
      stats: { total_jobs: 1 },
      onboarding: {
        completedSteps: ['talent_pool', 'candidate_search', 'cv_parser', 'interview_list', 'credits'],
      },
    })
    expect(screen.queryByText('Get started')).not.toBeInTheDocument()
  })

  it('can be hidden', () => {
    setup()

    fireEvent.click(screen.getByRole('button', { name: 'Hide the Get started list' }))

    expect(mockOnboarding.dismissChecklist).toHaveBeenCalledTimes(1)
  })

  it('offers to run the tour', () => {
    const onShowTour = vi.fn()
    setup({ onShowTour })

    fireEvent.click(screen.getByRole('button', { name: 'Show me around' }))

    expect(onShowTour).toHaveBeenCalledTimes(1)
  })
})
