import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act, within } from '@testing-library/react'
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
import { EXAMPLE_VIEW_DEFAULT } from '@/components/onboarding/tourSteps'
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
const addToInterviewList = (index = 0) =>
  fireEvent.click(screen.getAllByRole('button', { name: 'Add to interview list' })[index])
const noWrites = () => {
  expect(api.post).not.toHaveBeenCalled()
  expect(api.put).not.toHaveBeenCalled()
  expect(api.patch).not.toHaveBeenCalled()
  expect(api.delete).not.toHaveBeenCalled()
}

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

  describe('the interview list button', () => {
    it('is on every applicant, as on the real page', () => {
      renderPage()

      expect(screen.getAllByRole('button', { name: 'Add to interview list' })).toHaveLength(3)
    })

    it('puts a person on the interview list and takes them off again', () => {
      renderPage()

      addToInterviewList(0)
      expect(screen.getByRole('button', { name: 'Remove from interview list' })).toHaveTextContent('On interview list')
      fireEvent.click(tab('Interview List'))
      expect(screen.getByText('Amaka Obi')).toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: 'Remove from interview list' }))
      expect(screen.getByText('No one on the interview list yet')).toBeInTheDocument()
    })

    it('is on the Talent Pipeline rows too, and feeds the same list', () => {
      renderPage()
      fireEvent.click(tab('Talent Pipeline'))

      addToInterviewList(0)
      fireEvent.click(tab('Interview List'))

      expect(screen.getByText('Segun Adeyemi')).toBeInTheDocument()
    })

    it('starts with an empty interview list and says how to fill it', () => {
      renderPage()

      fireEvent.click(tab('Interview List'))

      expect(screen.getByText('No one on the interview list yet')).toBeInTheDocument()
      expect(screen.getByText(/Add candidates from Applicants, Talent Pipeline/)).toBeInTheDocument()
    })
  })

  describe('the Talent Pipeline tab and the Talent Pool', () => {
    it('shows CVs scored against the job, one still being read', () => {
      renderPage()

      fireEvent.click(tab('Talent Pipeline'))

      expect(screen.getByRole('button', { name: /Upload CVs/ })).toBeInTheDocument()
      expect(screen.getByText('Not yet scored')).toBeInTheDocument()
    })

    it('opens the Talent Pool from Upload CVs, without uploading anything', () => {
      renderPage()
      fireEvent.click(tab('Talent Pipeline'))

      fireEvent.click(screen.getByRole('button', { name: /Upload CVs/ }))

      expect(screen.getByRole('heading', { name: 'Talent Pool' })).toBeInTheDocument()
      expect(screen.getByText('Pipeline view (no job selected)')).toBeInTheDocument()
      noWrites()
    })

    it('opens the upload drawer from Add CV with the same wording as the real one', () => {
      renderPage()
      act(() => tourOptions.setView({ ...EXAMPLE_VIEW_DEFAULT, page: 'pool' }))

      fireEvent.click(screen.getByRole('button', { name: /Add CV/ }))

      const drawer = screen.getByRole('dialog', { name: 'Add to Talent Pool' })
      expect(drawer).toHaveTextContent('Upload up to 20 CVs (batch processed)')
      expect(drawer).toHaveTextContent('Drop PDFs here')
      expect(drawer).toHaveTextContent('Attach to Job')
      expect(drawer).toHaveTextContent('No job (add to pipeline only)')
      expect(within(drawer).getByRole('button', { name: 'Add to Talent Pool' })).toBeDisabled()
    })

    it('says scoring runs by itself once a job is chosen for the upload', () => {
      renderPage()
      act(() => tourOptions.setView({ ...EXAMPLE_VIEW_DEFAULT, page: 'pool', drawer: true }))
      expect(screen.queryByText(/AI scoring will run automatically/)).not.toBeInTheDocument()

      fireEvent.change(screen.getByLabelText(/Attach to Job/), { target: { value: 'sales' } })

      expect(screen.getByText(/AI scoring will run automatically after parsing/)).toBeInTheDocument()
    })

    it('ranks the pool against the chosen job, best match first', () => {
      renderPage()
      act(() => tourOptions.setView({ ...EXAMPLE_VIEW_DEFAULT, page: 'pool' }))
      expect(screen.getByText('Select a job to enable AI ranking')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Score all/ })).not.toBeInTheDocument()

      fireEvent.change(screen.getByLabelText('View against job:'), { target: { value: 'sales' } })

      expect(screen.getByText('Ranked by AI score')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Score all/ })).toBeInTheDocument()
      expect(screen.getByText('Showing candidates ranked against Sales Manager')).toBeInTheDocument()
      const names = screen.getAllByText(/Segun Adeyemi|Halima Yusuf|Ifeanyi Okoro/).map((el) => el.textContent)
      expect(names).toEqual(['Segun Adeyemi', 'Halima Yusuf', 'Ifeanyi Okoro'])
    })

    it('goes back to the example job', () => {
      renderPage()
      act(() => tourOptions.setView({ ...EXAMPLE_VIEW_DEFAULT, page: 'pool' }))

      fireEvent.click(screen.getByRole('button', { name: /Back to the example job/ }))

      expect(screen.getByRole('heading', { name: 'Applicants for Sales Manager' })).toBeInTheDocument()
    })
  })

  it('lets the tour put the page in the state a step needs', () => {
    renderPage()
    expect(tab('Applicants')).toHaveAttribute('aria-selected', 'true')

    act(() => tourOptions.setView({ ...EXAMPLE_VIEW_DEFAULT, tab: 'interviews', dialog: true, listed: ['a1', 'p1'] }))

    expect(tab('Interview List')).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Segun Adeyemi')).toBeInTheDocument()

    act(() => tourOptions.setView({ ...EXAMPLE_VIEW_DEFAULT, reasoning: true }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('Strengths')).toBeInTheDocument()
  })

  it('tells an employer who is charged what an interview costs, with the real numbers', async () => {
    renderPage()
    addToInterviewList(0)
    fireEvent.click(tab('Interview List'))

    expect(await screen.findByText(/costs 8 credits/)).toBeInTheDocument()
    expect(screen.getByText(/Your balance: 120/)).toBeInTheDocument()
  })

  it('falls back to a general sentence when nothing is charged', async () => {
    renderPage({ charged: false })
    addToInterviewList(0)
    fireEvent.click(tab('Interview List'))

    expect(await screen.findByText(/Each AI interview uses credits/)).toBeInTheDocument()
  })

  it('opens the send dialog with the cost, and sends nothing', async () => {
    renderPage()
    addToInterviewList(0)
    fireEvent.click(tab('Interview List'))
    await screen.findByText(/costs 8 credits/)

    fireEvent.click(screen.getAllByRole('button', { name: /Send interview link$/ })[0])

    const dialog = screen.getByRole('dialog', { name: 'Send AI interview invite?' })
    expect(dialog).toHaveTextContent('Amaka Obi will get an email invite')
    expect(dialog).toHaveTextContent('costs 8 credits')
    expect(dialog).toHaveTextContent('nothing is sent from here')

    fireEvent.click(screen.getByRole('button', { name: 'Send interview invite' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    noWrites()
  })

  it('never writes anything, whatever is pressed', async () => {
    renderPage()
    addToInterviewList(0)
    fireEvent.click(tab('Talent Pipeline'))
    fireEvent.click(screen.getByRole('button', { name: /Upload CVs/ }))
    fireEvent.click(screen.getByRole('button', { name: /Add CV/ }))
    fireEvent.change(screen.getByLabelText(/Attach to Job/), { target: { value: 'sales' } })
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    fireEvent.click(screen.getByRole('button', { name: /Back to the example job/ }))
    fireEvent.click(tab('Interview List'))
    fireEvent.click(await screen.findByRole('button', { name: /Send interview link to all/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Skip' }))

    noWrites()
    // The only request is the read-only price lookup.
    expect(api.get).toHaveBeenCalledTimes(1)
    expect(api.get).toHaveBeenCalledWith('/api/v1/interviews/pricing')
  })

  it('passes the real cost sentence to the tour only when the account is charged', async () => {
    renderPage()
    await waitFor(() => expect(tourOptions.costText).toMatch(/costs 8 credits/))
  })
})
