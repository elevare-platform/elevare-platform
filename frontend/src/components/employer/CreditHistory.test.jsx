import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn() } }))

import api from '@/lib/api'
import CreditHistory from './CreditHistory'

const line = (id, overrides = {}) => ({
  id,
  created_at: '2026-10-19T10:00:00Z',
  kind: 'grant',
  description: 'Credits added by Elevare',
  detail: null,
  credits_change: 5,
  plan_credits_change: 0,
  purchased_credits_change: 5,
  ...overrides,
})

describe('CreditHistory', () => {
  beforeEach(() => vi.clearAllMocks())

  it('says so when there is no activity yet', async () => {
    api.get.mockResolvedValueOnce({ data: { items: [], next_cursor: null } })
    render(<CreditHistory />)

    expect(await screen.findByText(/no credit activity yet/i)).toBeInTheDocument()
  })

  it('shows each line with its wording, the job it was for and where the credits came from', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        items: [
          line('a', {
            description: 'AI interview invite',
            detail: 'Senior Accountant',
            credits_change: -10,
            plan_credits_change: -6,
            purchased_credits_change: -4,
          }),
          line('b', { description: 'Monthly plan credits', credits_change: 40, plan_credits_change: 40, purchased_credits_change: 0 }),
        ],
        next_cursor: null,
      },
    })
    render(<CreditHistory />)

    expect(await screen.findByText('AI interview invite')).toBeInTheDocument()
    expect(screen.getByText('Senior Accountant')).toBeInTheDocument()
    expect(screen.getByText('−10')).toBeInTheDocument()
    expect(screen.getByText('6 plan · 4 bought')).toBeInTheDocument()
    expect(screen.getByText('+40')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /load more/i })).not.toBeInTheDocument()
  })

  it('loads the next page when asked, and stops offering more at the end', async () => {
    api.get
      .mockResolvedValueOnce({ data: { items: [line('a', { description: 'First page line' })], next_cursor: 'c1' } })
      .mockResolvedValueOnce({ data: { items: [line('b', { description: 'Second page line' })], next_cursor: null } })
    render(<CreditHistory />)

    fireEvent.click(await screen.findByRole('button', { name: /load more/i }))

    expect(await screen.findByText('Second page line')).toBeInTheDocument()
    expect(screen.getByText('First page line')).toBeInTheDocument()
    expect(api.get).toHaveBeenLastCalledWith('/api/v1/credits/transactions', {
      params: { limit: 20, cursor: 'c1' },
    })
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /load more/i })).not.toBeInTheDocument()
    )
  })

  it('offers a retry when the history cannot be loaded', async () => {
    api.get.mockRejectedValueOnce(new Error('down'))
    api.get.mockResolvedValueOnce({ data: { items: [line('a', { description: 'Back again' })], next_cursor: null } })
    render(<CreditHistory />)

    expect(await screen.findByText(/could not load your credit history/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))

    expect(await screen.findByText('Back again')).toBeInTheDocument()
  })
})
