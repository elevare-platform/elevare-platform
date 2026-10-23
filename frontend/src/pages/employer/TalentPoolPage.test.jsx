import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))

const AUTH = { user: { role: 'EMPLOYER' } }
vi.mock('@/context/AuthContext', () => ({ useAuth: () => AUTH }))

// Heavy children that are irrelevant to the filters under test
vi.mock('@/components/layout/Navbar', () => ({ default: () => null }))
vi.mock('@/components/layout/Footer', () => ({ default: () => null }))
vi.mock('@/components/candidates/CandidateProfilePanel', () => ({ default: () => null }))
vi.mock('@/components/employer/SourcedCvModal', () => ({ default: () => null }))
vi.mock('@/components/employer/CandidateActionModal', () => ({ default: () => null }))

import api from '@/lib/api'
import TalentPoolPage from './TalentPoolPage'

const LIST_URL = '/api/v1/talent-pool'

function lastListParams() {
  const calls = api.get.mock.calls.filter(([url]) => url === LIST_URL)
  return calls[calls.length - 1]?.[1]?.params
}

async function renderPage() {
  render(
    <MemoryRouter>
      <TalentPoolPage />
    </MemoryRouter>
  )
  await waitFor(() => expect(lastListParams()).toBeDefined())
}

async function selectJob() {
  await screen.findByRole('option', { name: 'Accountant' })
  fireEvent.change(screen.getByDisplayValue(/pipeline view/i), { target: { value: 'job-1' } })
  await waitFor(() => expect(lastListParams().job_id).toBe('job-1'))
}

describe('TalentPoolPage filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockImplementation(async (url) => {
      if (url === '/api/v1/jobs/mine') return { data: { items: [{ id: 'job-1', title: 'Accountant' }] } }
      return { data: { items: [], next_cursor: null } }
    })
  })

  it('sends sort=score once a job is selected, and no min_score by default', async () => {
    await renderPage()
    await selectJob()

    expect(lastListParams().sort).toBe('score')
    expect(lastListParams().min_score).toBeUndefined()
  })

  it('sends min_score when typed, and the 55+ chip fills it in', async () => {
    await renderPage()
    await selectJob()

    fireEvent.change(screen.getByLabelText('Minimum score'), { target: { value: '70' } })
    await waitFor(() => expect(lastListParams().min_score).toBe('70'))

    fireEvent.click(screen.getByRole('button', { name: '55+' }))
    await waitFor(() => expect(lastListParams().min_score).toBe('55'))
  })

  it('ignores an out-of-range min score instead of sending it', async () => {
    await renderPage()
    await selectJob()

    fireEvent.change(screen.getByLabelText('Minimum score'), { target: { value: '150' } })
    await new Promise((r) => setTimeout(r, 600)) // longer than the debounce

    expect(lastListParams().min_score).toBeUndefined()
  })

  it('sends added_within_days and the newest sort', async () => {
    await renderPage()
    await selectJob()

    fireEvent.change(screen.getByLabelText('Added within'), { target: { value: '14' } })
    await waitFor(() => expect(lastListParams().added_within_days).toBe('14'))

    fireEvent.change(screen.getByLabelText('Sort by'), { target: { value: 'newest' } })
    await waitFor(() => expect(lastListParams().sort).toBe('newest'))
  })

  it('without a job, offers only the recency filter (scores are per job)', async () => {
    await renderPage()

    expect(screen.queryByLabelText('Minimum score')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Sort by')).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Added within'), { target: { value: '7' } })
    await waitFor(() => expect(lastListParams().added_within_days).toBe('7'))
    expect(lastListParams().sort).toBeUndefined()
    expect(lastListParams().min_score).toBeUndefined()
  })
})

describe('TalentPoolPage jobs to attach CVs to', () => {
  const DRAFT = { id: 'job-9', title: 'National Sales Manager', status: 'DRAFT' }

  function renderAt(url) {
    return render(
      <MemoryRouter initialEntries={[url]}>
        <TalentPoolPage />
      </MemoryRouter>
    )
  }

  function mockApi({ mine = [], byId = {} } = {}) {
    api.get.mockImplementation(async (url) => {
      if (url === '/api/v1/jobs/mine') return { data: { items: mine } }
      const job = Object.entries(byId).find(([id]) => url === `/api/v1/jobs/${id}`)
      if (job) return { data: job[1] }
      if (url.startsWith('/api/v1/jobs/')) throw { response: { status: 404 } }
      return { data: { items: [], next_cursor: null } }
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
    AUTH.user = { role: 'EMPLOYER' }
  })

  it('asks for all of the user\'s jobs, not only the active ones, so a draft can be chosen', async () => {
    mockApi({ mine: [DRAFT] })
    renderAt('/')

    await screen.findByRole('option', { name: 'National Sales Manager' })
    const call = api.get.mock.calls.find(([url]) => url === '/api/v1/jobs/mine')
    expect(call[1].params).toMatchObject({ filter: 'all', limit: 100 })
  })

  it('shows a job from the address that is not one of the user\'s own, such as an admin working on a client\'s job', async () => {
    AUTH.user = { role: 'ADMIN' }
    mockApi({ mine: [], byId: { 'job-9': DRAFT } })
    renderAt('/?job_id=job-9')

    expect(await screen.findByRole('option', { name: 'National Sales Manager' })).toBeInTheDocument()
    expect(await screen.findByText(/ranked against National Sales Manager/)).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith('/api/v1/jobs/job-9')
  })

  it('groups the picker into Active and Drafts, and leaves closed jobs out of it', async () => {
    mockApi({
      mine: [
        { id: 'a', title: 'Accountant', status: 'ACTIVE' },
        DRAFT,
        { id: 'c', title: 'Old Role', status: 'CLOSED' },
      ],
    })
    const { container } = renderAt('/')
    await screen.findByRole('option', { name: 'Accountant' })

    const optionsIn = (label) =>
      [...container.querySelectorAll(`optgroup[label="${label}"] option`)].map((o) => o.textContent)
    expect(optionsIn('Active')).toEqual(['Accountant'])
    expect(optionsIn('Drafts (not yet published)')).toEqual(['National Sales Manager'])
    expect(screen.queryByRole('option', { name: 'Old Role' })).not.toBeInTheDocument()
  })

  it('still shows a closed job that is named in the address, so the choice is not blank', async () => {
    mockApi({ mine: [{ id: 'c', title: 'Old Role', status: 'CLOSED' }] })
    const { container } = renderAt('/?job_id=c')

    expect(await screen.findByRole('option', { name: 'Old Role' })).toBeInTheDocument()
    expect(container.querySelector('optgroup[label="Closed"] option')).not.toBeNull()
  })

  it('does not fetch the job separately when it is already one of the user\'s own', async () => {
    mockApi({ mine: [DRAFT] })
    renderAt('/?job_id=job-9')

    await screen.findByRole('option', { name: 'National Sales Manager' })
    expect(api.get).not.toHaveBeenCalledWith('/api/v1/jobs/job-9')
  })

  it('copes with a job in the address that this user cannot open', async () => {
    mockApi({ mine: [], byId: {} })
    renderAt('/?job_id=job-404')

    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/v1/jobs/job-404'))
    expect(screen.queryByRole('option', { name: /job-404/ })).not.toBeInTheDocument()
  })

  it('opens the Add CV drawer with the job from the address already chosen', async () => {
    mockApi({ mine: [DRAFT] })
    renderAt('/?job_id=job-9')
    await screen.findByRole('option', { name: 'National Sales Manager' })

    fireEvent.click(screen.getByRole('button', { name: /add cv/i }))

    // The drawer's "Attach to Job" dropdown is the one whose first option is "No job".
    const noJob = await screen.findByRole('option', { name: /no job \(add to pipeline only\)/i })
    expect(noJob.closest('select')).toHaveValue('job-9')
    expect(screen.getByText(/AI scoring will run automatically after parsing/)).toBeInTheDocument()
  })
})

describe('TalentPoolPage, profiles with no score', () => {
  const PROFILES = [
    { id: 'p-unreadable', candidate_name: 'Unreadable Una', status: 'new', source: 'email', created_at: '2026-10-01T10:00:00Z', ai_score: null, ai_score_failure: 'CV_UNREADABLE' },
    { id: 'p-failed', candidate_name: 'Failed Femi', status: 'new', source: 'email', created_at: '2026-10-01T10:00:00Z', ai_score: null, ai_score_failure: 'SCORING_FAILED' },
    { id: 'p-waiting', candidate_name: 'Waiting Wale', status: 'new', source: 'email', created_at: '2026-10-01T10:00:00Z', ai_score: null },
  ]

  function mockApi() {
    api.get.mockImplementation(async (url) => {
      if (url === '/api/v1/jobs/mine') return { data: { items: [{ id: 'job-1', title: 'Accountant' }] } }
      if (url === '/api/v1/talent-pool') return { data: { items: PROFILES, next_cursor: null, total: 3 } }
      return { data: { items: [], next_cursor: null } }
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
    AUTH.user = { role: 'EMPLOYER' }
    mockApi()
  })

  it('says why in the pipeline view, and keeps "Unscored" for a profile that is simply waiting', async () => {
    render(<MemoryRouter><TalentPoolPage /></MemoryRouter>)
    await screen.findByText('Unreadable Una')

    expect(screen.getByText('Could not read CV')).toHaveAttribute('title', expect.stringMatching(/Nothing could be read/))
    expect(screen.getByText('Scoring unavailable')).toBeInTheDocument()
    expect(screen.getAllByText('Unscored')).toHaveLength(1)
  })

  it('says why in the job view, in the score badge', async () => {
    render(<MemoryRouter><TalentPoolPage /></MemoryRouter>)
    await screen.findByRole('option', { name: 'Accountant' })
    fireEvent.change(screen.getByDisplayValue(/pipeline view/i), { target: { value: 'job-1' } })
    await screen.findByText('Unreadable Una')

    expect(screen.getByText('Could not read CV')).toBeInTheDocument()
    expect(screen.getByText('Scoring unavailable')).toBeInTheDocument()
    expect(screen.getByText('Not yet scored')).toBeInTheDocument()
  })
})

describe('TalentPoolPage, uploading a CV that may already be in the pool', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    AUTH.user = { role: 'EMPLOYER' }
    api.get.mockImplementation(async (url) => {
      if (url === '/api/v1/jobs/mine') return { data: { items: [{ id: 'job-1', title: 'Accountant' }] } }
      return { data: { items: [], next_cursor: null } }
    })
  })

  async function uploadAndGet(results) {
    api.post.mockResolvedValueOnce({ data: { results } })
    render(<MemoryRouter><TalentPoolPage /></MemoryRouter>)
    fireEvent.click(await screen.findByRole('button', { name: /add cv/i }))
    const pdf = new File(['%PDF-1.4'], 'cv.pdf', { type: 'application/pdf' })
    fireEvent.change(document.getElementById('tp-drawer-file'), { target: { files: [pdf] } })
    fireEvent.click(await screen.findByRole('button', { name: /add 1 cv to talent pool/i }))
  }

  it('says a CV that was already in the pool without a job has been added to this job', async () => {
    await uploadAndGet([
      { filename: 'chidi.pdf', status: 'attached', profile_id: 'p1', submission_id: null, linked_job_id: 'job-1' },
    ])

    expect(await screen.findByText('Already in pool, added to this job')).toBeInTheDocument()
    expect(screen.queryByText('Queued')).not.toBeInTheDocument()
  })

  it('says a duplicate was not added again, and which kind it was', async () => {
    await uploadAndGet([
      { filename: 'a.pdf', status: 'duplicate', profile_id: 'p1', submission_id: null, linked_job_id: null },
      { filename: 'b.pdf', status: 'duplicate', profile_id: 'p2', submission_id: null, linked_job_id: 'job-1' },
    ])

    expect(await screen.findByText('Already in pool')).toBeInTheDocument()
    expect(screen.getByText('Already in pool, for a job')).toBeInTheDocument()
  })

  it('still shows a file that failed with its reason', async () => {
    await uploadAndGet([{ filename: 'bad.pdf', status: 'failed', error: 'bad.pdf is not a valid PDF' }])

    expect(await screen.findByText('bad.pdf is not a valid PDF')).toBeInTheDocument()
  })

  it('says when this month\'s upload allowance is spent, with a way to upgrade', async () => {
    const message = 'Your plan includes 10 CV uploads a month and you have used 10. It resets on 1 December. Upgrade your plan to continue.'
    await uploadAndGet([
      { filename: 'full.pdf', status: 'limit_reached', error: message },
      { filename: 'known.pdf', status: 'duplicate', profile_id: 'p1', submission_id: null, linked_job_id: null },
    ])

    expect(await screen.findByText(/10 CV uploads a month/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Upgrade plan' })).toHaveAttribute('href', '/pricing')
    // A duplicate in the same batch is still reported as added to nothing, not as a failure.
    expect(screen.getByText('Already in pool')).toBeInTheDocument()
  })

  it('shows the plan\'s own message when the whole upload is refused', async () => {
    api.post.mockRejectedValueOnce({
      response: {
        status: 403,
        data: { code: 'PLAN_LIMIT_REACHED', message: 'Your plan includes 10 CV uploads a month and you have used 10. It resets on 1 December. Upgrade your plan to continue.' },
      },
    })
    render(<MemoryRouter><TalentPoolPage /></MemoryRouter>)
    fireEvent.click(await screen.findByRole('button', { name: /add cv/i }))
    const pdf = new File(['%PDF-1.4'], 'cv.pdf', { type: 'application/pdf' })
    fireEvent.change(document.getElementById('tp-drawer-file'), { target: { files: [pdf] } })
    fireEvent.click(await screen.findByRole('button', { name: /add 1 cv to talent pool/i }))

    expect(await screen.findByText(/10 CV uploads a month/)).toBeInTheDocument()
    expect(screen.queryByText('Upload failed. Please try again.')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Upgrade plan' })).toBeInTheDocument()
  })
})
