import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// Mock auth context
vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({ user: null, logout: vi.fn(), authReady: true }),
  getPostAuthRedirect: vi.fn(),
}))

import Navbar from './Navbar'

function renderNavbar() {
  return render(
    <MemoryRouter>
      <Navbar />
    </MemoryRouter>
  )
}

describe('Navbar', () => {
  it('renders the Elevare logo', () => {
    renderNavbar()
    expect(screen.getAllByAltText(/elevare human solutions/i).length).toBeGreaterThan(0)
  })

  it('renders login and register links when unauthenticated', () => {
    renderNavbar()
    expect(screen.getByRole('link', { name: /login/i })).toHaveAttribute('href', '/login')
    expect(screen.getByRole('link', { name: /register/i })).toHaveAttribute('href', '/register')
  })
})
