import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

vi.mock('@/lib/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

// Everything around the tab is irrelevant here. useTalentMatches is NOT mocked: the point is
// that the real hook reads the server's "needs Professional" refusal.
vi.mock('@/hooks/useCredits', () => ({
  useCredits: () => ({ balance: 5, loading: false, refetch: vi.fn() }),
}))
vi.mock('@/hooks/useSavedCandidates', () => ({
  useSavedCandidates: () => ({ isSaved: () => false, toggle: vi.fn() }),
}))
vi.mock('@/hooks/useInterviewList', () => ({
  useInterviewList: () => ({ isOnList: () => false, toggle: vi.fn() }),
}))
vi.mock('@/components/layout/Navbar', () => ({ default: () => null }))
vi.mock('@/components/layout/Footer', () => ({ default: () => null }))
vi.mock('@/components/candidates/CandidateProfilePanel', () => ({ default: () => null }))
vi.mock('@/components/employer/SourcedCvModal', () => ({ default: () => null }))
vi.mock('@/components/employer/CandidateActionModal', () => ({ default: () => null }))
vi.mock('@/components/employer/InterviewBriefSetupModal', () => ({ default: () => null }))
vi.mock('@/components/employer/InterviewDetailModal', () => ({ default: () => null }))
vi.mock('@/components/employer/TalentMatchCard', () => ({
  default: ({ match }) => <div>match: {match.candidate_name}</div>,
}))

import api from '@/lib/api'
import ApplicantsPage from './ApplicantsPage'

function renderMatchesTab(matchesResponse) {
  api.get.mockImplementation(async (url) => {
    if (url === '/api/v1/jobs/job-1/talent-matches') return matchesResponse()
    if (url === '/api/v1/rescore/jobs/job-1') return { data: { applications: 0, pipeline: 0, total: 0 } }
    if (url === '/api/v1/applications/job/job-1') return { data: { items: [], next_cursor: null } }
    return { data: { items: [] } }
  })
  return render(
    <MemoryRouter initialEntries={['/employer/jobs/job-1/applicants?tab=ai-matches']}>
      <Routes>
        <Route path="/employer/jobs/:jobId/applicants" element={<ApplicantsPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ApplicantsPage, AI Talent Matches tab and the plan', () => {
  beforeEach(() => vi.clearAllMocks())

  it('tells a Starter company the feature is part of Professional, with a link to the plans', async () => {
    renderMatchesTab(async () => {
      throw { response: { status: 403, data: { code: 'PLAN_UPGRADE_REQUIRED', message: 'This feature requires a Professional plan or above' } } }
    })

    expect(await screen.findByText('Talent Matches is part of the Professional plan')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'See plans' })).toHaveAttribute('href', '/pricing')
    // Not shown as a red error, and none of the normal tab furniture is left behind.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByText('No matches found')).not.toBeInTheDocument()
  })

  it('shows the matches to a company that has the feature', async () => {
    renderMatchesTab(async () => ({
      data: { items: [{ profile_id: 'p1', candidate_name: 'Funmilayo Adebayo' }] },
    }))

    expect(await screen.findByText('match: Funmilayo Adebayo')).toBeInTheDocument()
    expect(screen.queryByText('Talent Matches is part of the Professional plan')).not.toBeInTheDocument()
  })

  it('still shows any other failure as an error, not as an upgrade message', async () => {
    renderMatchesTab(async () => {
      throw { response: { status: 500, data: { code: 'INTERNAL_ERROR', message: 'Something broke' } } }
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('Something broke')
    expect(screen.queryByText('Talent Matches is part of the Professional plan')).not.toBeInTheDocument()
  })
})
