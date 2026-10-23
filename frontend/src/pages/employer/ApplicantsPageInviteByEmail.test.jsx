import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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

const PERSON = {
  id: 'entry-1',
  talent_pool_profile_id: 'p-1',
  candidate_name: 'Ada Obi',
  ownership: 'own_sourced',
  has_cv_access: true,
  email_only: false,
  interview_status: null,
}
const EMAIL_ONLY = {
  id: 'entry-2',
  talent_pool_profile_id: 'p-2',
  candidate_name: 'boss@example.com',
  ownership: 'own_sourced',
  has_cv_access: false,
  email_only: true,
  interview_status: 'PENDING',
}

function renderTab({ brief = 'Probe system design.', entries = [PERSON] } = {}) {
  api.get.mockImplementation(async (url) => {
    if (url === '/api/v1/interviews/pricing') {
      return { data: { credits_per_interview: 10, balance: 50, charged: true, plan_credits: 0, style: 'live' } }
    }
    if (url === '/api/v1/interview-list') return { data: { items: entries } }
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

describe('ApplicantsPage, Interview List tab, invite by email', () => {
  beforeEach(() => vi.clearAllMocks())

  it('offers the email form above the list once the interview is set up', async () => {
    renderTab()

    expect(await screen.findByRole('form', { name: 'Invite by email' })).toBeInTheDocument()
    expect(screen.getByText('Ada Obi')).toBeInTheDocument()
  })

  it('offers it before anyone is on the list, and says so in the empty message', async () => {
    renderTab({ entries: [] })

    expect(await screen.findByText('No one on the interview list yet')).toBeInTheDocument()
    expect(screen.getByRole('form', { name: 'Invite by email' })).toBeInTheDocument()
    expect(screen.getByText(/or send the interview to an email address/)).toBeInTheDocument()
  })

  it('does not offer it before the interview is set up, when there is nothing to send', async () => {
    renderTab({ brief: '' })

    expect(await screen.findByRole('button', { name: /Set up AI interview/ })).toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Invite by email' })).not.toBeInTheDocument()
  })

  it('shows an email-only row by its address, with the interview status and nothing to open', async () => {
    renderTab({ entries: [EMAIL_ONLY] })

    expect(await screen.findByText('boss@example.com')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /View CV|View Profile|Request Introduction/ })).not.toBeInTheDocument()
    expect(screen.getByText(/Sent: awaiting response|awaiting/i)).toBeInTheDocument()
  })

  it('still shows the view button for a real candidate in the same list', async () => {
    renderTab({ entries: [PERSON, EMAIL_ONLY] })

    expect(await screen.findByRole('button', { name: /View CV/ })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /View CV/ })).toHaveLength(1)
  })

  it('refreshes the list after sending, so the new address appears in it', async () => {
    renderTab({ entries: [] })
    api.post.mockResolvedValue({ data: { sent: true, reason: null, talent_pool_profile_id: 'p-2' } })
    const listCalls = () => api.get.mock.calls.filter(([url]) => url === '/api/v1/interview-list').length
    await screen.findByText('No one on the interview list yet')
    const before = listCalls()

    fireEvent.change(screen.getByRole('textbox', { name: "Candidate's email address" }), {
      target: { value: 'boss@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Send interview$/ }))

    await waitFor(() => expect(listCalls()).toBeGreaterThan(before))
    expect(api.post).toHaveBeenCalledWith('/api/v1/interviews/jobs/job-1/invite-by-email', { email: 'boss@example.com' })
  })
})
