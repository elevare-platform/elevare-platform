import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

vi.mock('@/lib/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

// Hooks and chrome that are irrelevant to the Talent Pipeline tab
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

const POOL_URL = '/api/v1/talent-pool'

function poolCalls() {
  return api.get.mock.calls.filter(([url]) => url === POOL_URL).map(([, cfg]) => cfg.params)
}
const lastPoolParams = () => poolCalls().at(-1)

function profile(id, overrides = {}) {
  return {
    id,
    candidate_name: `Candidate ${id}`,
    candidate_email: `${id}@example.com`,
    status: 'new',
    ai_score: 70,
    created_at: new Date(Date.now() - 3 * 86_400_000).toISOString(),
    ai_score_computed_at: new Date(Date.now() - 86_400_000).toISOString(),
    ...overrides,
  }
}

function renderPipelineTab() {
  return render(
    <MemoryRouter initialEntries={['/employer/jobs/job-1/applicants?tab=pipeline']}>
      <Routes>
        <Route path="/employer/jobs/:jobId/applicants" element={<ApplicantsPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ApplicantsPage, Talent Pipeline tab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockImplementation(async (url) => {
      if (url === POOL_URL) return { data: { items: [profile('a')], next_cursor: null, total: 1 } }
      return { data: { items: [] } }
    })
  })

  it('loads a page of 50 sorted by score, with age labels on rows', async () => {
    renderPipelineTab()

    expect(await screen.findByText('Candidate a')).toBeInTheDocument()
    expect(lastPoolParams()).toMatchObject({ job_id: 'job-1', limit: 50, sort: 'score' })
    expect(lastPoolParams().min_score).toBeUndefined()
    expect(screen.getByText(/Added 3d ago · Scored 1d ago/)).toBeInTheDocument()
    expect(screen.getByText('Showing 1 of 1')).toBeInTheDocument()
  })

  it('sends min_score from the 55+ chip and added_within_days from the date filter', async () => {
    renderPipelineTab()
    await screen.findByText('Candidate a')

    fireEvent.click(screen.getByRole('button', { name: '55+' }))
    await waitFor(() => expect(lastPoolParams().min_score).toBe('55'))

    fireEvent.change(screen.getByLabelText('Added within'), { target: { value: '14' } })
    await waitFor(() => expect(lastPoolParams().added_within_days).toBe('14'))
    expect(lastPoolParams().min_score).toBe('55')
  })

  it('"Load more" fetches the next page with the cursor and appends it', async () => {
    api.get.mockImplementation(async (url, cfg) => {
      if (url !== POOL_URL) return { data: { items: [] } }
      if (cfg.params.cursor === 'next-1') {
        return { data: { items: [profile('b')], next_cursor: null, total: 2 } }
      }
      return { data: { items: [profile('a')], next_cursor: 'next-1', total: 2 } }
    })
    renderPipelineTab()
    await screen.findByText('Candidate a')

    fireEvent.click(screen.getByRole('button', { name: 'Load more' }))

    expect(await screen.findByText('Candidate b')).toBeInTheDocument()
    expect(screen.getByText('Candidate a')).toBeInTheDocument()
    expect(lastPoolParams().cursor).toBe('next-1')
    expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument()
  })

  it('shows an error, not "No pipeline profiles yet", when loading fails', async () => {
    api.get.mockImplementation(async (url) => {
      if (url === POOL_URL) throw new Error('network')
      return { data: { items: [] } }
    })
    renderPipelineTab()

    expect(await screen.findByRole('alert')).toHaveTextContent(/failed to load the talent pipeline/i)
    expect(screen.queryByText('No pipeline profiles yet')).not.toBeInTheDocument()
  })
})
