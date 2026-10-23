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
vi.mock('@/components/employer/ShareInterviewResults', () => ({ default: () => null }))
// The detail window is replaced by a button that does what the real one does after a reinstate.
vi.mock('@/components/employer/InterviewDetailModal', () => ({
  default: ({ onReinstated, onClose }) => (
    <div role="dialog" aria-label="Interview detail">
      <button onClick={() => onReinstated?.({ status: 'PENDING' })}>pretend it was reinstated</button>
      <button onClick={onClose}>close the window</button>
    </div>
  ),
}))

import api from '@/lib/api'
import ApplicantsPage from './ApplicantsPage'

const entry = (status) => ({
  id: 'entry-1',
  talent_pool_profile_id: 'p-1',
  candidate_name: 'Ada Obi',
  ownership: 'own_sourced',
  has_cv_access: true,
  interview_status: status,
})

function renderList(status) {
  api.get.mockImplementation(async (url) => {
    if (url === '/api/v1/interviews/pricing') {
      return { data: { credits_per_interview: 10, balance: 50, charged: true, plan_credits: 0, style: 'strict' } }
    }
    if (url === '/api/v1/interview-list') return { data: { items: [entry(status)] } }
    if (url === '/api/v1/jobs/job-1') return { data: { id: 'job-1', title: 'Engineer', interview_brief: 'Probe design.' } }
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

describe('ApplicantsPage, Interview List, an interview that ended early', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows an interview that ended early with a way to review it, and no Resend', async () => {
    renderList('ENDED_CONDUCT')

    expect(await screen.findByText('Ended early')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Review and reinstate/ })).toBeInTheDocument()
    // This candidate's own Resend and Send buttons (the list's "send to all" button is another).
    expect(screen.queryByRole('button', { name: 'Resend' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Send interview link' })).not.toBeInTheDocument()
  })

  it('shows an interview the candidate stopped as stopped by them', async () => {
    renderList('STOPPED')

    expect(await screen.findByText('Stopped by the candidate')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Review and reinstate/ })).toBeInTheDocument()
  })

  it('opens the review window from the button', async () => {
    renderList('ENDED_CONDUCT')

    fireEvent.click(await screen.findByRole('button', { name: /Review and reinstate/ }))

    expect(screen.getByRole('dialog', { name: 'Interview detail' })).toBeInTheDocument()
  })

  it('goes back to "sent" with a Resend button once the interview is reinstated', async () => {
    renderList('ENDED_CONDUCT')
    fireEvent.click(await screen.findByRole('button', { name: /Review and reinstate/ }))

    fireEvent.click(screen.getByRole('button', { name: 'pretend it was reinstated' }))
    fireEvent.click(screen.getByRole('button', { name: 'close the window' }))

    expect(await screen.findByText('Sent: awaiting response')).toBeInTheDocument()
    expect(screen.queryByText('Ended early')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Resend' })).toBeInTheDocument()
  })

  it('still shows a finished interview as completed, with the usual review button', async () => {
    renderList('SCORED')

    expect(await screen.findByText('Completed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Review AI Interview/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Review and reinstate/ })).not.toBeInTheDocument()
  })
})
