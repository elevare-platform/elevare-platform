import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))
vi.mock('@/components/layout/Navbar', () => ({ default: () => null }))
vi.mock('@/components/layout/Footer', () => ({ default: () => null }))

// The tour itself is tested on its own; here it is a stand-in that records how the page
// started it and lets a test close it.
let tourOptions
const start = vi.fn()
vi.mock('@/components/onboarding/useExampleJobTour', () => ({
  useExampleJobTour: (options) => {
    tourOptions = options
    return { start }
  },
}))

const navigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal()),
  useNavigate: () => navigate,
}))

import api from '@/lib/api'
import ExampleJobTourPage from './ExampleJobTourPage'

const CHARGED = {
  charged: true,
  credits_per_interview: 8,
  balance: 120,
  plan_credits: 0,
}

function renderPage(pricing = CHARGED) {
  api.get.mockResolvedValue({ data: pricing })
  return render(
    <MemoryRouter>
      <ExampleJobTourPage />
    </MemoryRouter>
  )
}

const tab = (name) => screen.getByRole('tab', { name })

describe('ExampleJobTourPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('says plainly that the job and the people are made up', () => {
    renderPage()

    expect(screen.getByText(/The candidates and scores are made up/)).toBeInTheDocument()
    expect(screen.getByText(/no credits are used/)).toBeInTheDocument()
  })

  it('starts the tour by itself, and goes back to the dashboard when it closes', () => {
    renderPage()

    expect(tourOptions.autoStart).toBe(true)
    tourOptions.onClosed('SKIPPED')

    expect(navigate).toHaveBeenCalledWith('/dashboard')
  })

  it('can run the tour again', () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Replay the tour' }))

    expect(start).toHaveBeenCalledTimes(1)
  })

  it('shows applicants with their stage and an AI score', () => {
    renderPage()

    expect(screen.getByText('Amaka Obi')).toBeInTheDocument()
    // Once as Amaka's stage, once as a choice in the Move to list.
    expect(screen.getAllByText('Shortlisted').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByLabelText(/AI score: /).length).toBeGreaterThanOrEqual(3)
  })

  it('shows the reasons behind a score when it is pressed', () => {
    renderPage()
    expect(screen.queryByText('Strengths')).not.toBeInTheDocument()

    fireEvent.click(screen.getAllByLabelText(/AI score: /)[0])

    expect(screen.getByText('Strengths')).toBeInTheDocument()
    expect(screen.getByText('Gaps')).toBeInTheDocument()
  })

  it('lets the tour put the page in the state a step needs', async () => {
    renderPage()
    expect(tab('Applicants')).toHaveAttribute('aria-selected', 'true')

    act(() => tourOptions.setView({ tab: 'interviews', reasoning: false, dialog: true }))

    expect(tab('Interview List')).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    act(() => tourOptions.setView({ tab: 'applicants', reasoning: true, dialog: false }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('Strengths')).toBeInTheDocument()
  })

  it('shows CVs waiting to be scored on the Talent Pipeline tab', () => {
    renderPage()

    fireEvent.click(tab('Talent Pipeline'))

    expect(screen.getByRole('button', { name: /Upload CVs/ })).toBeInTheDocument()
    expect(screen.getByText('Not yet scored')).toBeInTheDocument()
  })

  it('does not upload anything when Upload CVs is pressed, and says so', () => {
    renderPage()
    fireEvent.click(tab('Talent Pipeline'))

    fireEvent.click(screen.getByRole('button', { name: /Upload CVs/ }))

    expect(screen.getByRole('status')).toHaveTextContent('Nothing is uploaded from this example')
    expect(api.post).not.toHaveBeenCalled()
  })

  it('tells an employer who is charged what an interview costs, with the real numbers', async () => {
    renderPage()
    fireEvent.click(tab('Interview List'))

    expect(await screen.findByText(/costs 8 credits/)).toBeInTheDocument()
    expect(screen.getByText(/Your balance: 120/)).toBeInTheDocument()
  })

  it('falls back to a general sentence when nothing is charged', async () => {
    renderPage({ charged: false })
    fireEvent.click(tab('Interview List'))

    expect(await screen.findByText(/Each AI interview uses credits/)).toBeInTheDocument()
  })

  it('opens the send dialog with the cost, and sends nothing', async () => {
    renderPage()
    fireEvent.click(tab('Interview List'))
    await screen.findByText(/costs 8 credits/)

    fireEvent.click(screen.getAllByRole('button', { name: /Send interview link$/ })[0])

    const dialog = screen.getByRole('dialog', { name: 'Send AI interview invite?' })
    expect(dialog).toHaveTextContent('Amaka Obi will get an email invite')
    expect(dialog).toHaveTextContent('costs 8 credits')
    expect(dialog).toHaveTextContent('nothing is sent from here')

    fireEvent.click(screen.getByRole('button', { name: 'Send interview invite' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(api.post).not.toHaveBeenCalled()
  })

  it('never writes anything, whatever is pressed', async () => {
    renderPage()
    fireEvent.click(tab('Talent Pipeline'))
    fireEvent.click(screen.getByRole('button', { name: /Upload CVs/ }))
    fireEvent.click(tab('Interview List'))
    fireEvent.click(await screen.findByRole('button', { name: /Send interview link to all/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Skip' }))

    expect(api.post).not.toHaveBeenCalled()
    expect(api.put).not.toHaveBeenCalled()
    expect(api.patch).not.toHaveBeenCalled()
    expect(api.delete).not.toHaveBeenCalled()
    // The only request is the read-only price lookup.
    expect(api.get).toHaveBeenCalledTimes(1)
    expect(api.get).toHaveBeenCalledWith('/api/v1/interviews/pricing')
  })

  it('passes the real cost sentence to the tour only when the account is charged', async () => {
    renderPage()
    await waitFor(() => expect(tourOptions.costText).toMatch(/costs 8 credits/))
  })
})
