import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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

const NOTHING_TO_RESCORE = { applications: 0, pipeline: 0, total: 0 }

function renderApplicants(items, rescoreStatus = NOTHING_TO_RESCORE) {
  api.get.mockImplementation(async (url) => {
    if (url === '/api/v1/applications/job/job-1') return { data: { items, next_cursor: null } }
    if (url === '/api/v1/rescore/jobs/job-1') return { data: rescoreStatus }
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

    fireEvent.click(screen.getByRole('button', { name: 'Match score: Could not read CV' }))

    const panel = screen.getByRole('dialog', { name: 'Fit reasoning' })
    expect(panel).toHaveTextContent('Nothing could be read from this CV')
    // No made-up number or "match" wording for a candidate who was never scored.
    expect(panel).not.toHaveTextContent('raw:')
    expect(panel).not.toHaveTextContent('rather than a pass or fail')
  })

  it('says scoring was unavailable, and that it is not a low score', async () => {
    renderApplicants([application('a', { ai_score_failure: 'SCORING_FAILED' })])
    await screen.findByText('Applicant a')

    fireEvent.click(screen.getByRole('button', { name: 'Match score: Scoring unavailable' }))

    expect(screen.getByRole('dialog', { name: 'Fit reasoning' })).toHaveTextContent('not a low score')
  })

  it('keeps "Not yet scored" for an application that is simply waiting, with nothing to open', async () => {
    renderApplicants([application('a')])
    await screen.findByText('Applicant a')

    fireEvent.click(screen.getByRole('button', { name: 'Match score: Not yet scored' }))

    expect(screen.queryByRole('dialog', { name: 'Fit reasoning' })).not.toBeInTheDocument()
  })

  describe('Rescore', () => {
    const STARTED = { scoring: 2, reparsing: 1, in_progress: 0, no_stored_file: 0, remaining: 0 }
    const applicantFetches = () =>
      api.get.mock.calls.filter(([url]) => url === '/api/v1/applications/job/job-1').length

    it('offers nothing when everyone has a score', async () => {
      renderApplicants([application('a', { ai_score: 70, ai_fit_summary: 'Good.' })])
      await screen.findByText('Applicant a')

      expect(screen.queryByRole('region', { name: 'Rescore candidates' })).not.toBeInTheDocument()
    })

    it('says how many candidates have no score, and rescores them all when pressed', async () => {
      api.post.mockResolvedValue({ data: STARTED })
      renderApplicants(
        [application('a', { ai_score_failure: 'CV_UNREADABLE' })],
        { applications: 3, pipeline: 0, total: 3 },
      )
      await screen.findByText('3 candidates have no score')
      const before = applicantFetches()

      fireEvent.click(screen.getByRole('button', { name: 'Rescore' }))

      await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/v1/rescore/jobs/job-1', {}))
      expect(await screen.findByRole('status')).toHaveTextContent('Started 3 candidates, 1 CV is being read again')
      // The list is loaded again so the candidates that were reset no longer say "could not read".
      await waitFor(() => expect(applicantFetches()).toBeGreaterThan(before))
    })

    it('rescores one candidate from their score panel', async () => {
      api.post.mockResolvedValue({ data: { ...STARTED, scoring: 1, reparsing: 0 } })
      renderApplicants([application('a', { ai_score_failure: 'SCORING_FAILED' })])
      await screen.findByText('Applicant a')

      fireEvent.click(screen.getByRole('button', { name: 'Match score: Scoring unavailable' }))
      fireEvent.click(screen.getByRole('button', { name: 'Rescore this candidate' }))

      await waitFor(() => expect(api.post).toHaveBeenCalledWith(
        '/api/v1/rescore/jobs/job-1', { application_id: 'a' }
      ))
      expect(await screen.findByText(/Started 1 candidate/)).toBeInTheDocument()
    })

    it('offers no Rescore on a real score or on a candidate who is just waiting', async () => {
      renderApplicants([
        application('a', { ai_score: 70, ai_fit_summary: 'Good.' }),
        application('b'),
      ])
      await screen.findByText('Applicant a')

      fireEvent.click(screen.getByRole('button', { name: 'Match score: Strong match' }))
      expect(screen.queryByRole('button', { name: 'Rescore this candidate' })).not.toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: 'Match score: Not yet scored' }))
      expect(screen.queryByRole('button', { name: 'Rescore this candidate' })).not.toBeInTheDocument()
    })

    it('shows the plan limit with an upgrade link when the plan does not include it', async () => {
      api.post.mockRejectedValue({
        response: { data: { code: 'PLAN_UPGRADE_REQUIRED', message: 'This feature requires a Professional plan or above' } },
      })
      renderApplicants([], { applications: 2, pipeline: 0, total: 2 })
      await screen.findByText('2 candidates have no score')

      fireEvent.click(screen.getByRole('button', { name: 'Rescore' }))

      expect(await screen.findByText(/requires a Professional plan or above/)).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Upgrade plan' })).toBeInTheDocument()
    })
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

    fireEvent.click(screen.getByRole('button', { name: 'Match score: Strong match' }))

    const panel = screen.getByRole('dialog', { name: 'Fit reasoning' })
    expect(panel).toHaveTextContent('raw: 78/100')
    expect(panel).toHaveTextContent('A strong fit.')
  })
})
