import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))
vi.mock('@/lib/analytics', () => ({ trackEvent: vi.fn() }))

let mockUser = { role: 'CANDIDATE', account_status: 'ACTIVE', is_profile_complete: true }
vi.mock('@/context/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

import api from '@/lib/api'
import { ApplyButton } from './ApplyButton'
import ApplyModal from '@/components/candidate/ApplyModal'
import { applicationsClosed } from '@/lib/applicationDeadline'

const DAY = 24 * 60 * 60 * 1000
const past = () => new Date(Date.now() - 3 * DAY).toISOString()
const ahead = () => new Date(Date.now() + 3 * DAY).toISOString()

function renderButton(props) {
  return render(
    <MemoryRouter>
      <ApplyButton jobId="job-1" jobStatus="ACTIVE" {...props} />
    </MemoryRouter>
  )
}

describe('applicationsClosed', () => {
  it('is closed only when there is a deadline and it is in the past', () => {
    expect(applicationsClosed(null)).toBe(false)
    expect(applicationsClosed(undefined)).toBe(false)
    expect(applicationsClosed('not a date')).toBe(false)
    expect(applicationsClosed(ahead())).toBe(false)
    expect(applicationsClosed(past())).toBe(true)
  })
})

describe('ApplyButton and the application deadline', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUser = { role: 'CANDIDATE', account_status: 'ACTIVE', is_profile_complete: true }
    api.get.mockResolvedValue({ data: { has_applied: false } })
  })

  it('says applications are closed, instead of offering Apply, once the deadline has passed', async () => {
    renderButton({ deadline: past() })

    expect(await screen.findByTestId('applications-closed')).toHaveTextContent('Applications closed')
    expect(screen.queryByRole('button', { name: /apply now/i })).not.toBeInTheDocument()
  })

  it('still offers Apply while the deadline is ahead, or there is none', async () => {
    const { unmount } = renderButton({ deadline: ahead() })
    expect(await screen.findByRole('button', { name: 'Apply Now' })).toBeEnabled()
    unmount()

    renderButton({ deadline: null })
    expect(await screen.findByRole('button', { name: 'Apply Now' })).toBeEnabled()
  })

  it('tells someone who is not signed in, too', () => {
    mockUser = null
    renderButton({ deadline: past() })

    expect(screen.getByTestId('applications-closed')).toBeInTheDocument()
  })

  it('keeps showing "Already Applied" to a candidate who applied before the deadline', async () => {
    renderButton({ deadline: past(), initialApplied: true })

    expect(await screen.findByText('✓ Already Applied')).toBeInTheDocument()
    expect(screen.queryByTestId('applications-closed')).not.toBeInTheDocument()
  })

  it('shows an employer nothing', () => {
    mockUser = { role: 'EMPLOYER', account_status: 'ACTIVE' }
    const { container } = renderButton({ deadline: past() })

    expect(container).toBeEmptyDOMElement()
  })
})

describe('ApplyModal, when the server refuses', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockResolvedValue({ data: { items: [] } })
  })

  async function submitAndRead(rejection) {
    api.post.mockRejectedValue({ response: rejection })
    render(
      <MemoryRouter>
        <ApplyModal jobId="job-1" onClose={() => {}} onSuccess={() => {}} />
      </MemoryRouter>
    )
    const submit = await screen.findByRole('button', { name: /submit application|apply/i, hidden: false })
    fireEvent.click(submit)
  }

  it("shows the server's own reason, not 'Something went wrong'", async () => {
    await submitAndRead({
      status: 422,
      data: { code: 'JOB_DEADLINE_PAST', status: 'error', message: 'Job application deadline has passed.' },
    })

    expect(await screen.findByText('Job application deadline has passed.')).toBeInTheDocument()
    expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument()
  })

  it('still falls back to the generic line when the server gives no reason', async () => {
    await submitAndRead({ status: 500, data: {} })

    await waitFor(() => expect(screen.getByText(/something went wrong/i)).toBeInTheDocument())
  })
})
