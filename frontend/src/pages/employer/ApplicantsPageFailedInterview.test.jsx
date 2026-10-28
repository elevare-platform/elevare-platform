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
vi.mock('@/components/employer/ShareInterviewResults', () => ({ default: () => null }))
vi.mock('@/components/employer/InterviewDetailModal', () => ({ default: () => null }))

import api from '@/lib/api'
import ApplicantsPage from './ApplicantsPage'

const entry = (status, failure) => ({
  id: 'entry-1',
  talent_pool_profile_id: 'p-1',
  candidate_name: 'Ada Obi',
  ownership: 'own_sourced',
  has_cv_access: true,
  interview_status: status,
  ...(failure === undefined ? {} : { interview_failure: failure }),
})

function renderList(status, failure) {
  api.get.mockImplementation(async (url) => {
    if (url === '/api/v1/interviews/pricing') {
      return { data: { credits_per_interview: 10, balance: 50, charged: true, plan_credits: 0, style: 'strict' } }
    }
    if (url === '/api/v1/interview-list') return { data: { items: [entry(status, failure)] } }
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

const recovered = (extra = {}) => ({
  data: { outcome: 'reopened', status: 'PENDING', interview_url: 'https://app.test/interview/abc', email_sent: true, ...extra },
})

describe('ApplicantsPage, Interview List, correcting a name read wrongly from a CV', () => {
  beforeEach(() => vi.clearAllMocks())

  it('lets the person who sourced the CV correct the name, and shows it at once', async () => {
    api.patch.mockResolvedValueOnce({ data: { id: 'p-1', candidate_name: 'Lateef Jakande', name_overridden: true } })
    renderList('PENDING')

    fireEvent.click(await screen.findByRole('button', { name: 'Correct the name' }))
    fireEvent.change(screen.getByLabelText("Candidate's name"), { target: { value: 'Lateef Jakande' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save name' }))

    expect(await screen.findByText('Lateef Jakande')).toBeInTheDocument()
    expect(api.patch).toHaveBeenCalledWith('/api/v1/talent-pool/p-1/name', { name: 'Lateef Jakande' })
    expect(screen.getByText('(corrected)')).toBeInTheDocument()
  })
})

describe('ApplicantsPage, Interview List, an interview that failed', () => {
  beforeEach(() => vi.clearAllMocks())

  it('says the recording was not received, and offers to reopen it, when the interview never finished', async () => {
    renderList('FAILED', 'NEVER_FINISHED')

    expect(await screen.findByText('Recording not received')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reopen for the candidate' })).toBeInTheDocument()
    expect(screen.queryByText('Scoring failed')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Resend' })).not.toBeInTheDocument()
  })

  it('says scoring failed, with a way to review it and no resend, when the recording did arrive', async () => {
    renderList('FAILED', 'SCORING_FAILED')

    expect(await screen.findByText('Scoring failed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Review interview/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Resend' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reopen for the candidate' })).not.toBeInTheDocument()
  })

  it('retries scoring from the row, and says it is scoring again', async () => {
    api.post.mockResolvedValueOnce({ data: { queued: true } })
    renderList('FAILED', 'SCORING_FAILED')

    fireEvent.click(await screen.findByRole('button', { name: 'Retry scoring' }))

    expect(await screen.findByText(/Scoring again/)).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledWith('/api/v1/interviews/score', null, {
      params: { job_id: 'job-1', talent_pool_profile_id: 'p-1' },
    })
    expect(screen.queryByRole('button', { name: 'Retry scoring' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Review interview/ })).toBeInTheDocument()
  })

  it('shows the server’s words when the scoring retry is refused, and can be pressed again', async () => {
    api.post.mockRejectedValueOnce({ response: { data: { code: 'INSUFFICIENT_CREDITS', message: 'Not enough credits' } } })
    renderList('FAILED', 'SCORING_FAILED')

    fireEvent.click(await screen.findByRole('button', { name: 'Retry scoring' }))

    expect(await screen.findByText(/Not enough credits/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry scoring' })).toBeEnabled()
  })

  it('says the server could not be reached when the scoring retry gets no answer', async () => {
    api.post.mockRejectedValueOnce(new Error('network'))
    renderList('FAILED', 'SCORING_FAILED')

    fireEvent.click(await screen.findByRole('button', { name: 'Retry scoring' }))

    expect(await screen.findByText(/We could not reach the server/)).toBeInTheDocument()
  })

  it('offers no scoring retry for a recording that never arrived', async () => {
    renderList('FAILED', 'NEVER_FINISHED')

    await screen.findByText('Recording not received')
    expect(screen.queryByRole('button', { name: 'Retry scoring' })).not.toBeInTheDocument()
    expect(screen.getByText(/uses one again/)).toBeInTheDocument()
  })

  it('keeps the old behaviour when the server does not say why it failed', async () => {
    renderList('FAILED')

    expect(await screen.findByText('Scoring failed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Resend' })).toBeInTheDocument()
  })

  it('reopens the interview, says the candidate was sent their link, and shows the row as sent', async () => {
    api.post.mockResolvedValueOnce(recovered())
    renderList('FAILED', 'NEVER_FINISHED')

    fireEvent.click(await screen.findByRole('button', { name: 'Reopen for the candidate' }))

    expect(await screen.findByText('The candidate was sent their link again.')).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledWith('/api/v1/interviews/p-1/recover', null, {
      params: { job_id: 'job-1', start_over: false },
    })
    expect(screen.getByText('Sent: awaiting response')).toBeInTheDocument()
    expect(screen.queryByText('Recording not received')).not.toBeInTheDocument()
  })

  it('shows the link to send by hand when there is no email on file', async () => {
    api.post.mockResolvedValueOnce(recovered({ email_sent: false }))
    renderList('FAILED', 'NEVER_FINISHED')

    fireEvent.click(await screen.findByRole('button', { name: 'Reopen for the candidate' }))

    expect(await screen.findByText(/There is no email on file/)).toBeInTheDocument()
    expect(screen.getByLabelText('Interview link')).toHaveValue('https://app.test/interview/abc')
  })

  it('says the recording was found, and shows the interview as completed, when the server completes it', async () => {
    api.post.mockResolvedValueOnce({ data: { outcome: 'completed', status: 'UPLOADED', interview_url: null, email_sent: false } })
    renderList('FAILED', 'NEVER_FINISHED')

    fireEvent.click(await screen.findByRole('button', { name: 'Reopen for the candidate' }))

    expect(await screen.findByText('The recording was found. It is being scored.')).toBeInTheDocument()
    expect(screen.getByText('Completed')).toBeInTheDocument()
  })

  it('asks before starting over, which deletes the answers, and does nothing if cancelled', async () => {
    renderList('FAILED', 'NEVER_FINISHED')

    fireEvent.click(await screen.findByRole('button', { name: 'Start over instead' }))
    expect(screen.getByRole('alert')).toHaveTextContent('deletes the answers')
    expect(api.post).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('starts over once confirmed', async () => {
    api.post.mockResolvedValueOnce(recovered({ outcome: 'started_over' }))
    renderList('FAILED', 'NEVER_FINISHED')

    fireEvent.click(await screen.findByRole('button', { name: 'Start over instead' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete and start over' }))

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/api/v1/interviews/p-1/recover', null, {
        params: { job_id: 'job-1', start_over: true },
      })
    )
    expect(await screen.findByText('The candidate was sent their link again.')).toBeInTheDocument()
  })

  it('shows the words the server gave when it refuses', async () => {
    api.post.mockRejectedValueOnce({
      response: { data: { code: 'INTERVIEW_NOT_RECOVERABLE', message: 'Only an interview that was started but never finished can be recovered.' } },
    })
    renderList('FAILED', 'NEVER_FINISHED')

    fireEvent.click(await screen.findByRole('button', { name: 'Reopen for the candidate' }))

    expect(await screen.findByText(/never finished can be recovered/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reopen for the candidate' })).toBeEnabled()
  })

  it('says the server could not be reached when there is no response', async () => {
    api.post.mockRejectedValueOnce(new Error('network'))
    renderList('FAILED', 'NEVER_FINISHED')

    fireEvent.click(await screen.findByRole('button', { name: 'Reopen for the candidate' }))

    expect(await screen.findByText(/We could not reach the server/)).toBeInTheDocument()
  })
})
