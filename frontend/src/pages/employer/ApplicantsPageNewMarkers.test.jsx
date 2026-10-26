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
const { toggleInterviewList } = vi.hoisted(() => ({ toggleInterviewList: vi.fn() }))
vi.mock('@/hooks/useInterviewList', () => ({
  useInterviewList: () => ({ isOnList: () => false, toggle: toggleInterviewList }),
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

const cvRow = (id, name, isNew) => ({ id, candidate_name: name, is_new: isNew, status: 'new' })

// `applicants` and `cvs` are the whole list; the server keeps only the new ones for unseen=true.
function renderPage({ applicants = [], applicantCount = 0, cvs = [], cvCount = 0, tab = '' }) {
  api.get.mockImplementation(async (url, config) => {
    const onlyNew = Boolean(config?.params?.unseen)
    if (url === '/api/v1/applications/job/job-1') {
      return { data: { items: onlyNew ? applicants.filter((a) => a.is_new) : applicants, next_cursor: null } }
    }
    if (url === '/api/v1/applications/job/job-1/new-count') return { data: { count: applicantCount } }
    if (url === '/api/v1/talent-pool/new-count') return { data: { count: cvCount } }
    if (url === '/api/v1/talent-pool') {
      const items = onlyNew ? cvs.filter((c) => c.is_new) : cvs
      return { data: { items, next_cursor: null, total: items.length } }
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

describe('ApplicantsPage, applicants not opened yet', () => {
  beforeEach(() => vi.clearAllMocks())

  it('badges the new applicants and counts them on the tab and on the page tab', async () => {
    renderPage({
      applicants: [application('a1', 'Ada New', { is_new: true }), application('a2', 'Bola Old')],
      applicantCount: 1,
    })

    expect(await screen.findByText('Ada New')).toBeInTheDocument()
    expect(screen.getAllByTestId('new-badge')).toHaveLength(1)
    expect(await screen.findByTestId('not-opened-count')).toHaveTextContent('1')
    expect(screen.getByTestId('applicants-new-count')).toHaveTextContent('1')
  })

  it('shows the tab with no count and no badge when nothing is new', async () => {
    renderPage({ applicants: [application('a2', 'Bola Old')], applicantCount: 0 })

    expect(await screen.findByText('Bola Old')).toBeInTheDocument()
    expect(screen.getByTestId('not-opened-tab')).toBeInTheDocument()
    expect(screen.queryByTestId('not-opened-count')).not.toBeInTheDocument()
    expect(screen.queryByTestId('applicants-new-count')).not.toBeInTheDocument()
    expect(screen.queryByTestId('new-badge')).not.toBeInTheDocument()
  })

  it('asks the server for only the unopened ones when the tab is chosen, and "All" brings the rest back', async () => {
    renderPage({
      applicants: [application('a1', 'Ada New', { is_new: true }), application('a2', 'Bola Old')],
      applicantCount: 1,
    })
    await screen.findByText('Bola Old')

    fireEvent.click(screen.getByTestId('not-opened-tab'))

    await waitFor(() => expect(screen.queryByText('Bola Old')).not.toBeInTheDocument())
    expect(screen.getByText('Ada New')).toBeInTheDocument()
    expect(screen.getByTestId('not-opened-tab')).toHaveAttribute('aria-selected', 'true')
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/applications/job/job-1',
      expect.objectContaining({ params: expect.objectContaining({ unseen: true }) })
    )

    fireEvent.click(screen.getByRole('tab', { name: 'All' }))

    expect(await screen.findByText('Bola Old')).toBeInTheDocument()
    expect(screen.getByTestId('not-opened-tab')).toHaveAttribute('aria-selected', 'false')
  })

  it('says every applicant has been opened when the tab is empty', async () => {
    renderPage({ applicants: [application('a2', 'Bola Old')], applicantCount: 0 })
    await screen.findByText('Bola Old')

    fireEvent.click(screen.getByTestId('not-opened-tab'))

    expect(await screen.findByText('You have opened every applicant')).toBeInTheDocument()
  })

  it('stops an applicant being new, and tells the server once, when their profile is opened', async () => {
    renderPage({ applicants: [application('a1', 'Ada New', { is_new: true })], applicantCount: 1 })
    await screen.findByText('Ada New')

    fireEvent.click(screen.getByRole('button', { name: 'View profile' }))

    await waitFor(() => expect(screen.queryByTestId('new-badge')).not.toBeInTheDocument())
    expect(api.post).toHaveBeenCalledWith('/api/v1/applications/a1/seen')
    expect(api.post).toHaveBeenCalledTimes(1)
    // The counts go down with it.
    expect(screen.queryByTestId('not-opened-count')).not.toBeInTheDocument()
    expect(screen.queryByTestId('applicants-new-count')).not.toBeInTheDocument()
  })

  it('counts an applicant as opened when their AI insight is read', async () => {
    renderPage({ applicants: [application('a1', 'Ada New', { is_new: true, ai_score: 80 })], applicantCount: 1 })
    await screen.findByText('Ada New')

    fireEvent.click(screen.getByRole('button', { name: /AI score/ }))

    await waitFor(() => expect(screen.queryByTestId('new-badge')).not.toBeInTheDocument())
    expect(api.post).toHaveBeenCalledWith('/api/v1/applications/a1/seen')
  })

  it('counts an applicant as opened when they are moved to the interview list', async () => {
    renderPage({ applicants: [application('a1', 'Ada New', { is_new: true })], applicantCount: 1 })
    await screen.findByText('Ada New')

    fireEvent.click(screen.getByRole('button', { name: 'Add to interview list' }))

    await waitFor(() => expect(screen.queryByTestId('new-badge')).not.toBeInTheDocument())
    expect(api.post).toHaveBeenCalledWith('/api/v1/applications/a1/seen')
    expect(toggleInterviewList).toHaveBeenCalledWith({ candidateProfileId: 'p-a1' })
  })

  it('does not tell the server about an applicant who was not new', async () => {
    renderPage({ applicants: [application('a2', 'Bola Old')], applicantCount: 0 })
    await screen.findByText('Bola Old')

    fireEvent.click(screen.getByRole('button', { name: 'View profile' }))

    expect(api.post).not.toHaveBeenCalled()
  })
})

describe('ApplicantsPage, pipeline CVs not opened yet', () => {
  beforeEach(() => vi.clearAllMocks())

  it('counts them for this job on the page tab before the tab is opened', async () => {
    renderPage({ cvs: [cvRow('cv-1', 'Pipeline Pat', true)], cvCount: 1 })

    expect(await screen.findByTestId('pipeline-new-count')).toHaveTextContent('1')
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/talent-pool/new-count',
      expect.objectContaining({ params: { job_id: 'job-1' } })
    )
  })

  it('badges a new CV, counts it on the tab, and marks it opened when it is opened', async () => {
    renderPage({ cvs: [cvRow('cv-1', 'Pipeline Pat', true)], cvCount: 1, tab: '?tab=pipeline' })
    const row = (await screen.findByText('Pipeline Pat')).closest('button')
    expect(within(row).getByTestId('new-badge')).toBeInTheDocument()
    expect(screen.getByTestId('not-opened-count')).toHaveTextContent('1')

    fireEvent.click(row)

    expect(api.post).toHaveBeenCalledWith('/api/v1/talent-pool/cv-1/seen')
    await waitFor(() => expect(screen.queryByTestId('new-badge')).not.toBeInTheDocument())
    expect(screen.queryByTestId('not-opened-count')).not.toBeInTheDocument()
  })

  it('counts a CV as opened when it is moved to the interview list', async () => {
    renderPage({ cvs: [cvRow('cv-1', 'Pipeline Pat', true)], cvCount: 1, tab: '?tab=pipeline' })
    await screen.findByText('Pipeline Pat')

    fireEvent.click(screen.getByRole('button', { name: 'Add to interview list' }))

    expect(api.post).toHaveBeenCalledWith('/api/v1/talent-pool/cv-1/seen')
    await waitFor(() => expect(screen.queryByTestId('new-badge')).not.toBeInTheDocument())
    expect(toggleInterviewList).toHaveBeenCalledWith({
      talentPoolProfileId: 'cv-1',
      candidateProfileId: undefined,
    })
  })

  it('shows only the unopened CVs on the "Not opened yet" tab', async () => {
    renderPage({
      cvs: [cvRow('cv-1', 'Pipeline Pat', true), cvRow('cv-2', 'Seen Sam', false)],
      cvCount: 1,
      tab: '?tab=pipeline',
    })
    await screen.findByText('Seen Sam')

    fireEvent.click(screen.getByTestId('not-opened-tab'))

    await waitFor(() => expect(screen.queryByText('Seen Sam')).not.toBeInTheDocument())
    expect(screen.getByText('Pipeline Pat')).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/talent-pool',
      expect.objectContaining({ params: expect.objectContaining({ job_id: 'job-1', unseen: true }) })
    )
  })

  it('says every CV has been opened when the tab is empty', async () => {
    renderPage({ cvs: [cvRow('cv-2', 'Seen Sam', false)], cvCount: 0, tab: '?tab=pipeline' })
    await screen.findByText('Seen Sam')

    fireEvent.click(screen.getByTestId('not-opened-tab'))

    expect(await screen.findByText('You have opened every CV')).toBeInTheDocument()
  })
})
