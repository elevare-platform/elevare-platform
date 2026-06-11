import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { HelmetProvider } from 'react-helmet-async'

// Mock api
vi.mock('@/lib/api', () => ({
  default: { post: vi.fn() },
}))

// Mock analytics — no-op in tests
vi.mock('@/lib/analytics', () => ({
  trackEvent: vi.fn(),
}))

import api from '@/lib/api'
import ContactPage from './ContactPage'

function renderContact(search = '') {
  return render(
    <HelmetProvider>
      <MemoryRouter initialEntries={[`/contact${search}`]}>
        <ContactPage />
      </MemoryRouter>
    </HelmetProvider>
  )
}

describe('ContactPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the contact form', () => {
    renderContact()
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/message/i)).toBeInTheDocument()
  })

  it('shows success state after valid submission', async () => {
    api.post.mockResolvedValueOnce({ data: { message: "Thank you" } })

    renderContact()

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Jane Doe' } })
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'jane@example.com' } })
    fireEvent.change(screen.getByLabelText(/message/i), { target: { value: 'This is a test message long enough.' } })
    fireEvent.click(screen.getByRole('button', { name: /send message/i }))

    await waitFor(() => {
      expect(screen.getByText(/message sent/i)).toBeInTheDocument()
    })
  })

  it('shows error message on network failure', async () => {
    api.post.mockRejectedValueOnce({
      response: { data: { detail: 'Server error' } },
    })

    renderContact()

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Jane Doe' } })
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'jane@example.com' } })
    fireEvent.change(screen.getByLabelText(/message/i), { target: { value: 'This is a test message long enough.' } })
    fireEvent.click(screen.getByRole('button', { name: /send message/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })

  it('pre-selects employer_inquiry from URL param', () => {
    renderContact('?type=employer_inquiry')
    const select = screen.getByLabelText(/enquiry type/i)
    expect(select.value).toBe('employer_inquiry')
  })
})
