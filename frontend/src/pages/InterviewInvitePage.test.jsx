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

  it.each([
    ['NONE', /Only the questions on screen are asked, with no follow-up questions/],
    ['PROBES_ONLY', /from a list the employer prepared/],
    [undefined, /Up to two short follow-up questions may be asked/],
  ])('shows the rules for what happens after an answer (%s), as the employer chose', async (mode, shown) => {
    renderPage({ ...INFO, style: 'strict', follow_up_mode: mode })

    expect(await screen.findByText(shown)).toBeInTheDocument()
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

  it('shows an interview that ended for conduct as ended, with the company, and offers no way to start', async () => {
    renderPage({ ...INFO, style: 'strict', status: 'ENDED_CONDUCT', started: true })

    expect(await screen.findByTestId('ended-screen')).toBeInTheDocument()
    expect(screen.getByText('Your interview has ended')).toBeInTheDocument()
    expect(screen.getByText('Acme Nigeria Ltd · Sales Executive')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Start the interview|Continue the interview/ })).not.toBeInTheDocument()
  })

  it('shows an interview the candidate stopped as stopped', async () => {
    renderPage({ ...INFO, style: 'strict', status: 'STOPPED', started: true })

    expect(await screen.findByText('You stopped the interview')).toBeInTheDocument()
  })

  it('welcomes back a candidate whose interview the employer reinstated (waiting again, but started)', async () => {
    renderPage({ ...INFO, style: 'strict', status: 'PENDING', started: true })

    expect(await screen.findByText(/The employer has let you carry on/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue the interview' })).toBeInTheDocument()
  })

  it('offers to continue after a reload, without saying the employer reinstated anything', async () => {
    renderPage({ ...INFO, style: 'strict', status: 'IN_PROGRESS', started: true })

    expect(await screen.findByText(/counts as leaving the screen once/)).toBeInTheDocument()
    expect(screen.queryByText(/The employer has let you carry on/)).not.toBeInTheDocument()
  })

  it('still offers to continue when an older server does not say whether it was started', async () => {
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
