import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), put: vi.fn() } }))
// The navbar has its own requests (the notification bell); this page's request is
// what is under test, so the page chrome is left out.
vi.mock('@/components/layout/Navbar', () => ({ default: () => null }))
vi.mock('@/components/layout/Footer', () => ({ default: () => null }))

import api from '@/lib/api'
import EmailSettingsPage from './EmailSettingsPage'

const ON = { email: 'ada@example.com', emails_enabled: true }
const OFF = { email: 'ada@example.com', emails_enabled: false }

function renderPage() {
  return render(
    <MemoryRouter>
      <EmailSettingsPage />
    </MemoryRouter>
  )
}

const toggle = () => screen.findByRole('switch', { name: 'Receive emails from Elevare' })

describe('EmailSettingsPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows the address and that emails are on', async () => {
    api.get.mockResolvedValueOnce({ data: ON })
    renderPage()

    const control = await toggle()
    expect(control).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByText('ada@example.com')).toBeInTheDocument()
    expect(screen.getByText(/application updates, introductions/i)).toBeInTheDocument()
  })

  it('turns emails off and says what still arrives', async () => {
    api.get.mockResolvedValueOnce({ data: ON })
    api.put.mockResolvedValueOnce({ data: OFF })
    renderPage()

    fireEvent.click(await toggle())

    await waitFor(() => expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false'))
    expect(api.put).toHaveBeenCalledWith('/api/v1/email-preferences/me', { emails_enabled: false })
    expect(screen.getByText(/email verification, are still sent/i)).toBeInTheDocument()
  })

  it('turns them back on', async () => {
    api.get.mockResolvedValueOnce({ data: OFF })
    api.put.mockResolvedValueOnce({ data: ON })
    renderPage()

    fireEvent.click(await toggle())

    await waitFor(() => expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true'))
    expect(api.put).toHaveBeenCalledWith('/api/v1/email-preferences/me', { emails_enabled: true })
  })

  it('does not flip the switch when saving fails, and says so', async () => {
    api.get.mockResolvedValueOnce({ data: ON })
    api.put.mockRejectedValueOnce(new Error('network'))
    renderPage()

    fireEvent.click(await toggle())

    expect(await screen.findByRole('alert')).toHaveTextContent('could not save')
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true')
  })

  it('shows an error when the settings cannot be loaded', async () => {
    api.get.mockRejectedValueOnce(new Error('network'))
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('could not load')
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
  })
})
