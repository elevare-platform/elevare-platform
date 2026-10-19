import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

import api from '@/lib/api'
import UnsubscribePage from './UnsubscribePage'

function renderPage(search = '?token=abc.def') {
  return render(
    <MemoryRouter initialEntries={[`/unsubscribe${search}`]}>
      <UnsubscribePage />
    </MemoryRouter>
  )
}

const ON = { email: 'a***@example.com', emails_enabled: true }
const OFF = { email: 'a***@example.com', emails_enabled: false }

describe('UnsubscribePage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('only asks when the page opens: nothing is changed until the button is pressed', async () => {
    api.get.mockResolvedValueOnce({ data: ON })
    renderPage()

    expect(await screen.findByText('Stop emails to a***@example.com?')).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith('/api/v1/email-preferences/unsubscribe', {
      params: { token: 'abc.def' },
    })
    expect(api.post).not.toHaveBeenCalled()
  })

  it('turns emails off when the button is pressed, then offers to turn them back on', async () => {
    api.get.mockResolvedValueOnce({ data: ON })
    api.post.mockResolvedValueOnce({ data: OFF })
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Unsubscribe' }))

    expect(await screen.findByText("You're unsubscribed")).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledWith('/api/v1/email-preferences/unsubscribe', null, {
      params: { token: 'abc.def' },
    })
    expect(screen.getByRole('button', { name: 'Turn emails back on' })).toBeInTheDocument()
  })

  it('turns emails back on from the same page', async () => {
    api.get.mockResolvedValueOnce({ data: ON })
    api.post.mockResolvedValueOnce({ data: OFF }).mockResolvedValueOnce({ data: ON })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Unsubscribe' }))

    fireEvent.click(await screen.findByRole('button', { name: 'Turn emails back on' }))

    expect(await screen.findByText('Emails are back on')).toBeInTheDocument()
    expect(api.post).toHaveBeenLastCalledWith('/api/v1/email-preferences/resubscribe', null, {
      params: { token: 'abc.def' },
    })
  })

  it('says so when emails were already off, without asking again', async () => {
    api.get.mockResolvedValueOnce({ data: OFF })
    renderPage()

    expect(await screen.findByText('Emails are already off')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Unsubscribe' })).not.toBeInTheDocument()
  })

  it('explains that account emails like verification still arrive', async () => {
    api.get.mockResolvedValueOnce({ data: ON })
    renderPage()

    expect(await screen.findByText(/email verification/i)).toBeInTheDocument()
  })

  it('shows a clear message for a link that is not valid', async () => {
    api.get.mockRejectedValueOnce({ response: { data: { code: 'INVALID_UNSUBSCRIBE_TOKEN' } } })
    renderPage()

    expect(await screen.findByText('This link is not valid')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open email settings' })).toHaveAttribute(
      'href',
      '/settings/email'
    )
  })

  it('shows the same message without calling the server when there is no token', async () => {
    renderPage('')

    expect(await screen.findByText('This link is not valid')).toBeInTheDocument()
    expect(api.get).not.toHaveBeenCalled()
  })

  it('shows a retry when the server cannot be reached', async () => {
    api.get.mockRejectedValueOnce(new Error('network'))
    renderPage()

    expect(await screen.findByText('Something went wrong')).toBeInTheDocument()
  })

  it('shows an error if pressing the button fails, rather than claiming success', async () => {
    api.get.mockResolvedValueOnce({ data: ON })
    api.post.mockRejectedValueOnce(new Error('network'))
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Unsubscribe' }))

    await waitFor(() => expect(screen.getByText('Something went wrong')).toBeInTheDocument())
    expect(screen.queryByText("You're unsubscribed")).not.toBeInTheDocument()
  })
})
