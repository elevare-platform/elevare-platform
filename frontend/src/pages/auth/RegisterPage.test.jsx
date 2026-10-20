import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const registerUser = vi.fn()
vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({ register: registerUser, user: null, authReady: true }),
  getPostAuthRedirect: () => '/dashboard',
}))

import RegisterPage from './RegisterPage'

function renderForm() {
  return render(
    <MemoryRouter initialEntries={['/register?role=candidate']}>
      <RegisterPage />
    </MemoryRouter>
  )
}

const submit = () => fireEvent.click(screen.getByRole('button', { name: 'Create account' }))

describe('RegisterPage, name length', () => {
  beforeEach(() => vi.clearAllMocks())

  it('refuses a first name longer than an account can store, before anything is sent', async () => {
    renderForm()

    fireEvent.change(screen.getByLabelText('First name'), { target: { value: 'a'.repeat(31) } })
    submit()

    expect(await screen.findByText('First name must be 30 characters or fewer')).toBeInTheDocument()
    expect(registerUser).not.toHaveBeenCalled()
  })

  it('refuses a last name that is too long in the same way', async () => {
    renderForm()

    fireEvent.change(screen.getByLabelText('Last name'), { target: { value: 'b'.repeat(31) } })
    submit()

    expect(await screen.findByText('Last name must be 30 characters or fewer')).toBeInTheDocument()
  })

  it('has no complaint about a name of exactly 30 characters', async () => {
    renderForm()

    fireEvent.change(screen.getByLabelText('First name'), { target: { value: 'a'.repeat(30) } })
    fireEvent.change(screen.getByLabelText('Last name'), { target: { value: 'b'.repeat(30) } })
    submit()

    // The other fields are still empty, so the form is not sent, but the names are fine.
    await waitFor(() => expect(screen.getByText('Enter a valid email address')).toBeInTheDocument())
    expect(screen.queryByText(/characters or fewer/)).not.toBeInTheDocument()
  })
})
