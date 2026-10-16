import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

vi.mock('@/lib/api', () => ({ default: { post: vi.fn(), get: vi.fn() } }))

const AUTH = {
  user: null,
  authReady: true,
  completePasswordChange: vi.fn(),
  logout: vi.fn(),
}
vi.mock('@/context/AuthContext', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useAuth: () => AUTH }
})

import api from '@/lib/api'
import { getPostAuthRedirect } from '@/context/AuthContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import ChangePasswordPage from './ChangePasswordPage'

const TEMP = 'Temp-Pass-1!'
const NEW = 'Brand-New-Pass-2@'

const forcedEmployer = {
  id: 'u1',
  role: 'EMPLOYER',
  first_name: 'Samson',
  account_status: 'ACTIVE',
  must_change_password: true,
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/change-password']}>
      <Routes>
        <Route path="/change-password" element={<ChangePasswordPage />} />
        <Route path="/employer/onboarding" element={<p>Onboarding screen</p>} />
        <Route path="/login" element={<p>Login screen</p>} />
      </Routes>
    </MemoryRouter>
  )
}

function fill({ current = TEMP, next = NEW, confirm = NEW } = {}) {
  fireEvent.change(screen.getByLabelText(/temporary password|current password/i), { target: { value: current } })
  fireEvent.change(screen.getByLabelText(/^new password$/i), { target: { value: next } })
  fireEvent.change(screen.getByLabelText(/confirm new password/i), { target: { value: confirm } })
  fireEvent.click(screen.getByRole('button', { name: /save new password/i }))
}

describe('ChangePasswordPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    AUTH.user = forcedEmployer
  })

  it('explains the temporary password and offers sign out', () => {
    renderPage()

    expect(screen.getByText(/set up with a temporary password/i)).toBeInTheDocument()
    expect(screen.getByLabelText('Temporary password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign out/i })).toBeInTheDocument()
  })

  it('sends the three fields, starts the fresh session and continues to onboarding', async () => {
    const session = { access_token: 't', user: { ...forcedEmployer, must_change_password: false } }
    api.post.mockResolvedValue({ data: session })
    AUTH.completePasswordChange.mockResolvedValue({
      ...forcedEmployer,
      must_change_password: false,
      is_profile_complete: false,
    })
    renderPage()

    fill()

    expect(await screen.findByText('Onboarding screen')).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledWith('/api/v1/auth/change-password', {
      current_password: TEMP,
      new_password: NEW,
      confirm_password: NEW,
    })
    expect(AUTH.completePasswordChange).toHaveBeenCalledWith(session)
  })

  it('shows a wrong current password under that field and stays put', async () => {
    api.post.mockRejectedValue({
      response: { status: 400, data: { code: 'INVALID_CURRENT_PASSWORD' } },
    })
    renderPage()

    fill({ current: 'not-the-password' })

    expect(await screen.findByText('That is not your current password.')).toBeInTheDocument()
    expect(AUTH.completePasswordChange).not.toHaveBeenCalled()
    expect(screen.queryByText('Onboarding screen')).not.toBeInTheDocument()
  })

  it('catches a weak password before asking the server', async () => {
    renderPage()

    fill({ next: 'weak', confirm: 'weak' })

    expect(await screen.findByText(/at least 8 characters/i, { selector: 'p, span' })).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('shows a plain message for any other failure', async () => {
    api.post.mockRejectedValue({ response: { status: 500, data: {} } })
    renderPage()

    fill()

    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i)
  })

  it('sends someone with no session to the login page', () => {
    AUTH.user = null
    renderPage()

    expect(screen.getByText('Login screen')).toBeInTheDocument()
  })

  it('works for an ordinary user too, without the temporary-password wording or sign out', () => {
    AUTH.user = { ...forcedEmployer, must_change_password: false }
    renderPage()

    expect(screen.getByLabelText('Current password')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /sign out/i })).not.toBeInTheDocument()
  })

  it('signs out', async () => {
    AUTH.logout.mockResolvedValue()
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /sign out/i }))

    await waitFor(() => expect(AUTH.logout).toHaveBeenCalled())
  })
})

describe('where an account with a temporary password is sent', () => {
  beforeEach(() => {
    AUTH.user = forcedEmployer
  })

  it('getPostAuthRedirect sends it to the change screen before anything else', () => {
    expect(getPostAuthRedirect(forcedEmployer)).toBe('/change-password')
    expect(getPostAuthRedirect({ ...forcedEmployer, must_change_password: false, is_profile_complete: true })).toBe('/dashboard')
  })

  it('the route guard keeps it off every protected page', () => {
    render(
      <MemoryRouter initialEntries={['/employer/jobs']}>
        <Routes>
          <Route element={<ProtectedRoute allowedRoles={['EMPLOYER']} />}>
            <Route path="/employer/jobs" element={<p>Jobs page</p>} />
          </Route>
          <Route path="/change-password" element={<p>Change password screen</p>} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Change password screen')).toBeInTheDocument()
    expect(screen.queryByText('Jobs page')).not.toBeInTheDocument()
  })
})
