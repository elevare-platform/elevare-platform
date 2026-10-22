import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn() } }))
vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({ user: { first_name: 'Ada', last_name: 'Admin' }, logout: vi.fn() }),
}))
vi.mock('@/components/layout/NotificationBell', () => ({ default: () => null }))

import api from '@/lib/api'
import AdminLayout from './AdminLayout'

function renderLayout() {
  return render(
    <MemoryRouter>
      <AdminLayout>
        <p>page</p>
      </AdminLayout>
    </MemoryRouter>
  )
}

describe('AdminLayout, the badge on the Jobs link', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows how many jobs are waiting for review', async () => {
    api.get.mockResolvedValue({ data: { count: 3 } })
    renderLayout()

    expect(await screen.findByLabelText('3 waiting for review')).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith('/api/v1/admin/jobs/pending-count')
  })

  it('shows nothing when no job is waiting', async () => {
    api.get.mockResolvedValue({ data: { count: 0 } })
    renderLayout()

    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(screen.queryByLabelText(/waiting for review/)).not.toBeInTheDocument()
  })

  it('does not crowd the menu with a huge number', async () => {
    api.get.mockResolvedValue({ data: { count: 250 } })
    renderLayout()

    expect(await screen.findByLabelText('250 waiting for review')).toHaveTextContent('99+')
  })

  it('shows no badge, and no error, when the count cannot be read', async () => {
    api.get.mockRejectedValue(new Error('network'))
    renderLayout()

    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(screen.queryByLabelText(/waiting for review/)).not.toBeInTheDocument()
    expect(screen.getByText('page')).toBeInTheDocument()
  })
})
