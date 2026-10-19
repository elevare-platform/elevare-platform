import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/api', () => ({ default: { put: vi.fn(), get: vi.fn(), post: vi.fn(), delete: vi.fn() } }))
vi.mock('@/lib/analytics', () => ({ trackEvent: vi.fn() }))
vi.mock('@/components/layout/Navbar', () => ({ default: () => null }))
vi.mock('@/components/layout/Footer', () => ({ default: () => null }))

const updateUser = vi.fn()
vi.mock('@/context/AuthContext', () => ({ useAuth: () => ({ updateUser }) }))

let mockProfile
vi.mock('@/hooks/useCandidateProfile', () => ({
  useCandidateProfile: () => ({ profile: mockProfile, loading: false, error: null, refetch: vi.fn() }),
}))

const navigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal()),
  useNavigate: () => navigate,
}))

import api from '@/lib/api'
import { trackEvent } from '@/lib/analytics'
import CandidateProfilePage from './CandidateProfilePage'

const WITHOUT_CV = {
  bio: '',
  skills: ['Negotiation'],
  years_of_experience: 4,
  location: 'Lagos',
  cvs: [],
  work_experiences: [],
  educations: [],
  certifications: [],
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/candidate/profile?next=/jobs/42']}>
      <CandidateProfilePage />
    </MemoryRouter>
  )
}

async function fillAboutYouAndSave() {
  fireEvent.change(screen.getByLabelText('About You'), { target: { value: 'Sales professional' } })
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Save Profile' })) })
}

describe('CandidateProfilePage, finishing a profile', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.clearAllMocks()
    mockProfile = WITHOUT_CV
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('says a CV is still needed, and that it is not uploaded on this page', () => {
    renderPage()

    const note = screen.getByText('One more step: upload your CV').closest('[role="note"]')
    expect(note).toHaveTextContent('not on this page')
    expect(note.querySelector('a')).toHaveAttribute('href', '/candidate/dashboard/documents')
  })

  it('has no such notice once there is a CV', () => {
    mockProfile = { ...WITHOUT_CV, cvs: [{ id: 'c1' }] }
    renderPage()

    expect(screen.queryByText('One more step: upload your CV')).not.toBeInTheDocument()
  })

  it('keeps the person here after saving when the profile still needs a CV', async () => {
    api.put.mockResolvedValueOnce({ data: { is_profile_complete: false } })
    renderPage()

    await fillAboutYouAndSave()
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })

    expect(screen.getByText(/It still needs a CV/)).toBeInTheDocument()
    expect(navigate).not.toHaveBeenCalled()
    expect(trackEvent).not.toHaveBeenCalled()
    expect(updateUser).toHaveBeenCalledWith({ is_profile_complete: false })
  })

  it('sends the person back to where they came from once the profile is complete', async () => {
    mockProfile = { ...WITHOUT_CV, cvs: [{ id: 'c1' }] }
    api.put.mockResolvedValueOnce({ data: { is_profile_complete: true } })
    renderPage()

    await fillAboutYouAndSave()
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })

    expect(screen.queryByText(/It still needs a CV/)).not.toBeInTheDocument()
    expect(trackEvent).toHaveBeenCalledWith('Profile', 'profile_complete')
    expect(navigate).toHaveBeenCalledWith('/jobs/42', { replace: true })
  })
})
