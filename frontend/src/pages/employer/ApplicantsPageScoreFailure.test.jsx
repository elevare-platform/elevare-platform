import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

vi.mock('@/lib/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

// Hooks and chrome that are irrelevant to the applicants list
vi.mock('@/hooks/useTalentMatches', () => ({
  useTalentMatches: () => ({
    matches: [], loading: false, error: null, notReady: false, fetchTalentMatches: vi.fn(),
  }),
}))
vi.mock('@/hooks/useCredits', () => ({
  useCredits: () => ({ balance: 0, loading: false, refetch: vi.fn() }),
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

import api from '@/lib/api'
import ApplicantsPage from './ApplicantsPage'

function application(id, overrides = {}) {
  return {
    id,
    status: 'SUBMITTED',
    candidate_name: `Applicant ${id}`,
    candidate_profile_id: `profile-${id}`,
    status_updated_at: '2026-10-01T10:00:00Z',
    job_title: 'Accountant',
    ai_score: null,
    ...overrides,
  }
}

function renderApplicants(items) {
  api.get.mockImplementation(async (url) => {
    if (url === '/api/v1/applications/job/job-1') return { data: { items, next_cursor: null } }
    return { data: { items: [] } }
  })
  return render(
    <MemoryRouter initialEntries={['/employer/jobs/job-1/applicants']}>
      <Routes>
        <Route path="/employer/jobs/:jobId/applicants" element={<ApplicantsPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ApplicantsPage, applicants with no score', () => {
  beforeEach(() => vi.clearAllMocks())

  it('says the CV could not be read, and explains it when pressed', async () => {
    renderApplicants([application('a', { ai_score_failure: 'CV_UNREADABLE' })])
    await screen.findByText('Applicant a')

    fireEvent.click(screen.getByRole('button', { name: 'AI score: Could not read CV' }))

    const panel = screen.getByRole('dialog', { name: 'AI fit reasoning' })
    expect(panel).toHaveTextContent('Nothing could be read from this CV')
    // No made-up number or "match" wording for a candidate who was never scored.
    expect(panel).not.toHaveTextContent('raw:')
    expect(panel).not.toHaveTextContent('rather than a pass or fail')
  })

  it('says scoring was unavailable, and that it is not a low score', async () => {
    renderApplicants([application('a', { ai_score_failure: 'SCORING_FAILED' })])
    await screen.findByText('Applicant a')

    fireEvent.click(screen.getByRole('button', { name: 'AI score: Scoring unavailable' }))

    expect(screen.getByRole('dialog', { name: 'AI fit reasoning' })).toHaveTextContent('not a low score')
  })

  it('keeps "Not yet scored" for an application that is simply waiting, with nothing to open', async () => {
    renderApplicants([application('a')])
    await screen.findByText('Applicant a')

    fireEvent.click(screen.getByRole('button', { name: 'AI score: Not yet scored' }))

    expect(screen.queryByRole('dialog', { name: 'AI fit reasoning' })).not.toBeInTheDocument()
  })

  it('still shows a real score with its reasons', async () => {
    renderApplicants([
      application('a', {
        ai_score: 78,
        ai_fit_summary: 'A strong fit.',
        ai_strengths: ['Sales leadership'],
        ai_weaknesses: [],
      }),
    ])
    await screen.findByText('Applicant a')

    fireEvent.click(screen.getByRole('button', { name: 'AI score: Strong match' }))

    const panel = screen.getByRole('dialog', { name: 'AI fit reasoning' })
    expect(panel).toHaveTextContent('raw: 78/100')
    expect(panel).toHaveTextContent('A strong fit.')
  })
})
