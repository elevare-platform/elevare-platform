import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn() } }))
vi.mock('@/components/admin/AdminLayout', () => ({ default: ({ children }) => <div>{children}</div> }))
vi.mock('@/components/employer/InterviewDetailModal', () => ({
  default: ({ jobId, talentPoolProfileId, candidateName, onClose }) => (
    <div role="dialog" aria-label="Interview detail">
      <p>
        {jobId}/{talentPoolProfileId}/{candidateName}
      </p>
      <button onClick={onClose}>close the window</button>
    </div>
  ),
}))

import api from '@/lib/api'
import AdminJobInterviewsPage from './AdminJobInterviewsPage'

const ITEM = (extra) => ({
  id: `entry-${extra.talent_pool_profile_id}`,
  candidate_name: 'Ada Obi',
  current_title: 'Sales Manager',
  interview_status: 'SCORED',
  interview_score: 58,
  interview_reviewed: false,
  interview_failure: null,
  ...extra,
})

function mockApi(items, job = { title: 'Regional Sales Manager' }) {
  api.get.mockImplementation(async (url) => {
    if (url === '/api/v1/interview-list') return { data: { items, total: items.length } }
    if (url === '/api/v1/jobs/job-1') return { data: job }
    if (url === '/api/v1/interviews/jobs/job-1/score-visibility') return { data: { show_scores: true } }
    throw new Error(`unexpected ${url}`)
  })
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/admin/jobs/job-1/interviews']}>
      <Routes>
        <Route path="/admin/jobs/:jobId/interviews" element={<AdminJobInterviewsPage />} />
        <Route path="/admin/jobs" element={<p>the jobs page</p>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('AdminJobInterviewsPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('asks for the job’s whole interview list and names the job', async () => {
    mockApi([ITEM({ talent_pool_profile_id: 'p-1' })])
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Interviews: Regional Sales Manager' })).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith('/api/v1/interview-list', { params: { job_id: 'job-1' } })
  })

  it('lists each candidate with how the interview stands and the score shown', async () => {
    mockApi([
      ITEM({ talent_pool_profile_id: 'p-1' }),
      ITEM({ talent_pool_profile_id: 'p-2', candidate_name: 'Bola Ade', interview_status: 'PENDING', interview_score: null }),
      ITEM({ talent_pool_profile_id: 'p-3', candidate_name: 'Chidi Okafor', interview_status: 'FAILED', interview_failure: 'NEVER_FINISHED', interview_score: null }),
    ])
    renderPage()

    const ada = (await screen.findByText('Ada Obi')).closest('tr')
    expect(within(ada).getByText('Completed')).toBeInTheDocument()
    expect(within(ada).getByTestId('admin-score')).toHaveTextContent('58')
    expect(screen.getByText('Bola Ade').closest('tr')).toHaveTextContent('Sent: awaiting response')
    expect(screen.getByText('Chidi Okafor').closest('tr')).toHaveTextContent('Recording not received')
  })

  it('flags a reviewed score with the small tag', async () => {
    mockApi([ITEM({ talent_pool_profile_id: 'p-1', interview_score: 89, interview_reviewed: true })])
    renderPage()

    const row = (await screen.findByText('Ada Obi')).closest('tr')
    expect(within(row).getByTestId('admin-score')).toHaveTextContent('89')
    expect(within(row).getByTestId('reviewed-tag')).toBeInTheDocument()
  })

  it('offers to open only the interviews there is something to open for', async () => {
    mockApi([
      ITEM({ talent_pool_profile_id: 'p-1' }),
      ITEM({ talent_pool_profile_id: 'p-2', candidate_name: 'Bola Ade', interview_status: 'PENDING', interview_score: null }),
      ITEM({ talent_pool_profile_id: 'p-3', candidate_name: 'Dayo Bello', interview_status: null, interview_score: null }),
    ])
    renderPage()
    await screen.findByText('Ada Obi')

    expect(screen.getAllByRole('button', { name: /Review interview/ })).toHaveLength(1)
    expect(screen.getByText('Dayo Bello').closest('tr')).toHaveTextContent('Not invited yet')
  })

  it('opens the review window for the chosen candidate on this job, and reads the list again when it closes', async () => {
    mockApi([ITEM({ talent_pool_profile_id: 'p-1' })])
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: /Review interview/ }))
    expect(screen.getByRole('dialog', { name: 'Interview detail' })).toHaveTextContent('job-1/p-1/Ada Obi')

    api.get.mockClear()
    mockApi([ITEM({ talent_pool_profile_id: 'p-1', interview_score: 89, interview_reviewed: true })])
    fireEvent.click(screen.getByRole('button', { name: 'close the window' }))

    expect(await screen.findByTestId('reviewed-tag')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('says so when nobody is on the list', async () => {
    mockApi([])
    renderPage()

    expect(await screen.findByText("Nobody is on this job's interview list yet.")).toBeInTheDocument()
  })

  it('still shows the list when the job’s name cannot be read', async () => {
    api.get.mockImplementation(async (url) => {
      if (url === '/api/v1/interview-list') return { data: { items: [ITEM({ talent_pool_profile_id: 'p-1' })] } }
      throw new Error('no job')
    })
    renderPage()

    expect(await screen.findByText('Ada Obi')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Interviews' })).toBeInTheDocument()
  })

  it('says the job was not found, or that the list could not be loaded', async () => {
    api.get.mockImplementation(async (url) => {
      if (url === '/api/v1/interview-list') throw { response: { status: 404 } }
      throw new Error('other')
    })
    const first = renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('That job could not be found.')
    first.unmount()

    api.get.mockImplementation(async () => {
      throw new Error('network')
    })
    renderPage()
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('We could not load this job'))
  })

  it('links back to the jobs list', async () => {
    mockApi([])
    renderPage()

    fireEvent.click(await screen.findByRole('link', { name: /Back to jobs/ }))

    expect(screen.getByText('the jobs page')).toBeInTheDocument()
  })
})
