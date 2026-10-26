import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

vi.mock('@/lib/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
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
vi.mock('@/components/employer/InterviewBriefSetupModal', () => ({ default: () => null }))
vi.mock('@/components/employer/InterviewDetailModal', () => ({ default: () => null }))

import api from '@/lib/api'
import ApplicantsPage from './ApplicantsPage'

const application = (id, name, over = {}) => ({
  id,
  candidate_name: name,
  candidate_profile_id: `p-${id}`,
  status: 'SUBMITTED',
  status_updated_at: '2026-10-01T10:00:00Z',
  job_title: 'Engineer',
  is_new: false,
  ...over,
})

function renderPage({ items, count, tab = '' }) {
  api.get.mockImplementation(async (url, config) => {
    if (url === '/api/v1/applications/job/job-1') {
      const shown = config?.params?.unseen ? items.filter((a) => a.is_new) : items
      return { data: { items: shown, next_cursor: null } }
    }
    if (url === '/api/v1/applications/job/job-1/new-count') return { data: { count } }
    if (url === '/api/v1/talent-pool') {
      return {
        data: {
          items: [{ id: 'cv-1', candidate_name: 'Pipeline Pat', is_new: true, status: 'new' }],
          next_cursor: null,
          total: 1,
        },
      }
    }
    return { data: { items: [] } }
  })
  api.post.mockResolvedValue({ data: { seen: true } })
  return render(
    <MemoryRouter initialEntries={[`/employer/jobs/job-1/applicants${tab}`]}>
      <Routes>
        <Route path="/employer/jobs/:jobId/applicants" element={<ApplicantsPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ApplicantsPage, new applicants', () => {
  beforeEach(() => vi.clearAllMocks())

  it('marks the applicants who are new and says how many there are', async () => {
    renderPage({
      items: [application('a1', 'Ada New', { is_new: true }), application('a2', 'Bola Old')],
      count: 1,
    })

    expect(await screen.findByText('Ada New')).toBeInTheDocument()
    expect(await screen.findByText('1 new applicant you have not opened yet.')).toBeInTheDocument()
    expect(screen.getAllByTestId('new-badge')).toHaveLength(1)
  })

  it('shows no banner and no badge when nothing is new', async () => {
    renderPage({ items: [application('a2', 'Bola Old')], count: 0 })

    expect(await screen.findByText('Bola Old')).toBeInTheDocument()
    expect(screen.queryByTestId('new-applicants-banner')).not.toBeInTheDocument()
    expect(screen.queryByTestId('new-badge')).not.toBeInTheDocument()
  })

  it('asks the server for only the new ones when "Show new only" is pressed', async () => {
    renderPage({
      items: [application('a1', 'Ada New', { is_new: true }), application('a2', 'Bola Old')],
      count: 1,
    })
    await screen.findByText('Bola Old')

    fireEvent.click(screen.getByRole('button', { name: 'Show new only' }))

    await waitFor(() => expect(screen.queryByText('Bola Old')).not.toBeInTheDocument())
    expect(screen.getByText('Ada New')).toBeInTheDocument()
    expect(screen.getByText('Showing only the applicants you have not opened yet.')).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/applications/job/job-1',
      expect.objectContaining({ params: expect.objectContaining({ unseen: true }) })
    )
    expect(screen.getByRole('button', { name: 'Show all applicants' })).toBeInTheDocument()
  })

  it('stops an applicant being new, and tells the server once, when their profile is opened', async () => {
    renderPage({ items: [application('a1', 'Ada New', { is_new: true })], count: 1 })
    await screen.findByText('Ada New')

    fireEvent.click(screen.getByRole('button', { name: 'View profile' }))

    await waitFor(() => expect(screen.queryByTestId('new-badge')).not.toBeInTheDocument())
    expect(api.post).toHaveBeenCalledWith('/api/v1/applications/a1/seen')
    expect(api.post).toHaveBeenCalledTimes(1)
    // The banner count goes down with it, and with none left the banner goes.
    expect(screen.queryByTestId('new-applicants-banner')).not.toBeInTheDocument()
  })

  it('does not tell the server about an applicant who was not new', async () => {
    renderPage({ items: [application('a2', 'Bola Old')], count: 0 })
    await screen.findByText('Bola Old')

    fireEvent.click(screen.getByRole('button', { name: 'View profile' }))

    expect(api.post).not.toHaveBeenCalled()
  })

  it('marks a new pipeline CV and tells the server when it is opened', async () => {
    renderPage({ items: [], count: 0, tab: '?tab=pipeline' })
    const row = (await screen.findByText('Pipeline Pat')).closest('button')
    expect(within(row).getByTestId('new-badge')).toBeInTheDocument()

    fireEvent.click(row)

    expect(api.post).toHaveBeenCalledWith('/api/v1/talent-pool/cv-1/seen')
    await waitFor(() => expect(screen.queryByTestId('new-badge')).not.toBeInTheDocument())
  })
})
