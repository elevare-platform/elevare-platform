import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

vi.mock('@/lib/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('@/lib/strictInterview', async (importOriginal) => ({
  ...(await importOriginal()),
  checkDevice: vi.fn(() => ({ ok: true, problems: [] })),
}))

import api from '@/lib/api'
import InterviewInvitePage from './InterviewInvitePage'

const INFO = {
  job_title: 'Sales Executive',
  company_name: 'Acme Nigeria Ltd',
  status: 'PENDING',
  max_duration_minutes: 20,
  session_start_count: 0,
}

function renderPage(info) {
  api.get.mockResolvedValue({ data: info })
  return render(
    <MemoryRouter initialEntries={['/interview/tok123']}>
      <Routes>
        <Route path="/interview/:token" element={<InterviewInvitePage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('InterviewInvitePage, which interview the link opens', () => {
  beforeEach(() => vi.clearAllMocks())

  it('opens the strict interview when the invitation is a strict one', async () => {
    renderPage({ ...INFO, style: 'strict' })

    expect(await screen.findByText(/cannot be taken on a phone or a tablet/)).toBeInTheDocument()
    expect(screen.getByText('Acme Nigeria Ltd · Sales Executive')).toBeInTheDocument()
    expect(screen.getByText(/at most 20 minutes/)).toBeInTheDocument()
  })

  it('opens the live interview when the invitation is a live one', async () => {
    renderPage({ ...INFO, style: 'live' })

    expect(await screen.findByText(/earphones or headphones/i)).toBeInTheDocument()
    expect(screen.queryByText(/cannot be taken on a phone or a tablet/)).not.toBeInTheDocument()
  })

  it('opens the live interview when the server does not say, as an older server does not', async () => {
    renderPage(INFO)

    expect(await screen.findByText(/earphones or headphones/i)).toBeInTheDocument()
  })

  it('offers to continue when a strict interview was already started', async () => {
    renderPage({ ...INFO, style: 'strict', status: 'IN_PROGRESS' })

    expect(await screen.findByRole('button', { name: 'Continue the interview' })).toBeInTheDocument()
  })

  it('shows a finished strict interview as submitted', async () => {
    renderPage({ ...INFO, style: 'strict', status: 'UPLOADED' })

    expect(await screen.findByText('Interview submitted')).toBeInTheDocument()
  })

  it('says so when the link is no good', async () => {
    api.get.mockRejectedValue({ response: { data: { message: 'This interview invite link has expired' } } })
    render(
      <MemoryRouter initialEntries={['/interview/tok123']}>
        <Routes>
          <Route path="/interview/:token" element={<InterviewInvitePage />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByText('This interview invite link has expired')).toBeInTheDocument()
  })
})
