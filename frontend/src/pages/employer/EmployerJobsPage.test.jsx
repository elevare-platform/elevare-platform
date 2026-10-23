import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('@/components/layout/Navbar', () => ({ default: () => null }))
vi.mock('@/components/layout/Footer', () => ({ default: () => null }))
vi.mock('@/components/jobs/JobCard', () => ({
  JobCard: ({ job }) => <div data-testid="job-card">{job.title}</div>,
}))

import api from '@/lib/api'
import EmployerJobsPage from './EmployerJobsPage'

const DRAFT = { id: 'j-1', title: 'National Sales Manager', status: 'DRAFT', moderation_status: 'PENDING' }
const ACTIVE = { id: 'j-2', title: 'Accountant', status: 'ACTIVE', moderation_status: 'APPROVED' }

// The page also asks for the "ready to publish" count (filter=approved, limit 1);
// only the requests that fill the list matter here.
const listRequests = () =>
  api.get.mock.calls.filter(
    ([url, config]) => url === '/api/v1/jobs/mine' && config?.params?.filter !== 'approved'
  )
const lastListFilter = () => listRequests().at(-1)?.[1]?.params?.filter

function mockJobs(byFilter) {
  api.get.mockImplementation(async (url, config) => {
    if (url === '/api/v1/jobs/mine') {
      const items = byFilter[config?.params?.filter] ?? []
      return { data: { items, total: items.length, next_cursor: null } }
    }
    return { data: { kyc_status: 'APPROVED', is_profile_complete: true } }
  })
}

function renderPage() {
  return render(
    <MemoryRouter>
      <EmployerJobsPage />
    </MemoryRouter>
  )
}

describe('EmployerJobsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('opens on All, so a draft is there to see without hunting for its tab', async () => {
    mockJobs({ all: [DRAFT, ACTIVE] })
    renderPage()

    expect(await screen.findByText('National Sales Manager')).toBeInTheDocument()
    expect(lastListFilter()).toBe('all')
    expect(screen.getByRole('tab', { name: 'All' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Active' })).toHaveAttribute('aria-selected', 'false')
  })

  it('lists All first, since it is the one the page opens on', () => {
    mockJobs({})
    renderPage()

    const tabs = screen.getAllByRole('tab').map((tab) => tab.textContent.trim())
    expect(tabs[0]).toBe('All')
    expect(tabs).toContain('Active')
    expect(tabs).toContain('Pending review')
  })

  it('has a tab for the jobs the plan switched off, and asks the server for exactly those', async () => {
    const SWITCHED_OFF = { id: 'j-3', title: 'Sales Executive', status: 'DISABLED', moderation_status: 'APPROVED' }
    mockJobs({ all: [ACTIVE, SWITCHED_OFF], disabled: [SWITCHED_OFF] })
    renderPage()
    await screen.findByText('Accountant')

    fireEvent.click(screen.getByRole('tab', { name: 'Switched off' }))

    await waitFor(() => expect(lastListFilter()).toBe('disabled'))
    expect(await screen.findByText('Sales Executive')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText('Accountant')).not.toBeInTheDocument())
  })

  it('still lets the employer narrow to one status', async () => {
    mockJobs({ all: [DRAFT, ACTIVE], active: [ACTIVE] })
    renderPage()
    await screen.findByText('National Sales Manager')

    fireEvent.click(screen.getByRole('tab', { name: 'Active' }))

    await waitFor(() => expect(lastListFilter()).toBe('active'))
    await waitFor(() => expect(screen.queryByText('National Sales Manager')).not.toBeInTheDocument())
    expect(screen.getByText('Accountant')).toBeInTheDocument()
  })

  it('welcomes a new employer with no jobs at all, not a "No all jobs" message', async () => {
    mockJobs({ all: [] })
    renderPage()

    expect(await screen.findByText('No jobs yet')).toBeInTheDocument()
    expect(screen.getByText(/Post your first job to start finding candidates\./)).toBeInTheDocument()
    expect(screen.queryByText(/No all jobs/i)).not.toBeInTheDocument()
  })

  it('says so when one status has nothing, and offers the way back to All', async () => {
    mockJobs({ all: [DRAFT], rejected: [] })
    renderPage()
    await screen.findByText('National Sales Manager')

    fireEvent.click(screen.getByRole('tab', { name: 'Rejected' }))

    expect(await screen.findByText('No rejected jobs')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Back to all' }))
    expect(await screen.findByText('National Sales Manager')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'All' })).toHaveAttribute('aria-selected', 'true')
  })
})
