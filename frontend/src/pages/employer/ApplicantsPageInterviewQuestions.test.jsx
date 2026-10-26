import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

vi.mock('@/lib/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), put: vi.fn() },
}))
vi.mock('@/hooks/useTalentMatches', () => ({
  useTalentMatches: () => ({
    matches: [], loading: false, error: null, notReady: false, planRequired: false, fetchTalentMatches: vi.fn(),
  }),
}))
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
vi.mock('@/components/employer/InterviewDetailModal', () => ({ default: () => null }))
vi.mock('@/components/employer/ShareInterviewResults', () => ({ default: () => null }))

import api from '@/lib/api'
import ApplicantsPage from './ApplicantsPage'

const ENTRY = {
  id: 'entry-1',
  talent_pool_profile_id: 'p-1',
  candidate_name: 'Ada Obi',
  ownership: 'own_sourced',
  has_cv_access: true,
  interview_status: null,
}

function renderInterviewList({ style, brief = 'Probe system design.', entries = [ENTRY] }) {
  api.get.mockImplementation(async (url) => {
    if (url === '/api/v1/interviews/pricing') {
      return { data: { credits_per_interview: 10, balance: 50, charged: true, plan_credits: 0, style } }
    }
    if (url === '/api/v1/interview-list') return { data: { items: entries } }
    if (url.endsWith('/scoring-profile')) {
      return { data: { profile: null, templates: [], default_bands: { strong: 85, shortlist: 75, hold: 65 }, default_key_min_rating: 3 } }
    }
    if (url === '/api/v1/jobs/job-1') return { data: { id: 'job-1', title: 'Engineer', interview_brief: brief } }
    if (url === '/api/v1/rescore/jobs/job-1') return { data: { applications: 0, pipeline: 0, total: 0 } }
    return { data: { items: [] } }
  })
  return render(
    <MemoryRouter initialEntries={['/employer/jobs/job-1/applicants?tab=interview-list']}>
      <Routes>
        <Route path="/employer/jobs/:jobId/applicants" element={<ApplicantsPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ApplicantsPage, Interview List tab, the questions button', () => {
  beforeEach(() => vi.clearAllMocks())

  it('is offered when the platform uses the strict interview', async () => {
    renderInterviewList({ style: 'strict' })

    expect(await screen.findByRole('button', { name: /Interview questions/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Edit interview brief/ })).toBeInTheDocument()
  })

  it('offers the scoring profile beside it for the strict interview, and opens the editor', async () => {
    renderInterviewList({ style: 'strict' })

    fireEvent.click(await screen.findByRole('button', { name: /Scoring profile/ }))

    expect(await screen.findByRole('dialog', { name: 'Scoring profile' })).toBeInTheDocument()
  })

  it('does not offer the scoring profile with the live interview, which it never applies to', async () => {
    renderInterviewList({ style: 'live' })

    await screen.findByRole('button', { name: /Edit interview brief/ })
    expect(screen.queryByRole('button', { name: /Scoring profile/ })).not.toBeInTheDocument()
  })

  it('is not shown with the live interview, which has no questions to edit', async () => {
    renderInterviewList({ style: 'live' })

    expect(await screen.findByRole('button', { name: /Edit interview brief/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Interview questions/ })).not.toBeInTheDocument()
  })

  it('is not shown while the style is not known yet, so nothing flashes up', async () => {
    api.get.mockImplementation(async (url) => {
      if (url === '/api/v1/interviews/pricing') throw new Error('network')
      if (url === '/api/v1/interview-list') return { data: { items: [ENTRY] } }
      if (url === '/api/v1/jobs/job-1') return { data: { id: 'job-1', title: 'Engineer', interview_brief: 'x' } }
      return { data: { items: [] } }
    })
    render(
      <MemoryRouter initialEntries={['/employer/jobs/job-1/applicants?tab=interview-list']}>
        <Routes>
          <Route path="/employer/jobs/:jobId/applicants" element={<ApplicantsPage />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByRole('button', { name: /Edit interview brief/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Interview questions/ })).not.toBeInTheDocument()
  })

  it('is offered even before anyone is on the list, so the questions can be ready first', async () => {
    renderInterviewList({ style: 'strict', entries: [] })

    expect(await screen.findByText('No one on the interview list yet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Interview questions/ })).toBeInTheDocument()
  })

  it('is offered when there is no brief yet, since fixed questions need no brief', async () => {
    renderInterviewList({ style: 'strict', brief: '' })

    expect(await screen.findByRole('button', { name: /Set up AI interview/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Interview questions/ })).toBeInTheDocument()
  })
})
