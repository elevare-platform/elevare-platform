import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('@/components/admin/AdminLayout', () => ({
  default: ({ children }) => <div>{children}</div>,
}))

import api from '@/lib/api'
import AdminClientsPage from './AdminClientsPage'

const PROVISIONED = {
  user_id: 'u-1',
  organization_id: 'o-1',
  email: 'samson@colton.example.com',
  temporary_password: 'Kp7#mQ9wTz4!aB',
}

const writeText = vi.fn()

function type(label, value) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

function fillAccount(overrides = {}) {
  const v = {
    'First name': 'Samson',
    'Last name': 'Okafor',
    'Email address': 'samson@colton.example.com',
    'Company name': 'Colton Group',
    ...overrides,
  }
  Object.entries(v).forEach(([label, value]) => type(label, value))
  fireEvent.click(screen.getByRole('button', { name: /create account/i }))
}

function fillJob(overrides = {}) {
  const v = {
    'Job title': 'National Sales Manager',
    Location: 'Lagos, Nigeria',
    'About the role': 'Lead national sales for an FMCG brand.',
    'Key responsibilities': 'Own the national sales plan and distributors.',
    Requirements: 'Twelve years of progressive FMCG sales experience.',
    ...overrides,
  }
  Object.entries(v).forEach(([label, value]) => type(label, value))
  fireEvent.click(screen.getByRole('button', { name: /create draft job/i }))
}

async function createAccount() {
  api.post.mockResolvedValueOnce({ data: PROVISIONED })
  render(<AdminClientsPage />)
  fillAccount()
  await screen.findByText(/Account created for Colton Group/)
}

describe('AdminClientsPage: creating an account', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })
    writeText.mockResolvedValue()
  })

  it('creates the account and shows the login details once, with a warning', async () => {
    await createAccount()

    expect(api.post).toHaveBeenCalledWith('/api/v1/admin/employers/provision', {
      first_name: 'Samson',
      last_name: 'Okafor',
      email: 'samson@colton.example.com',
      phone_number: null,
      company_name: 'Colton Group',
    })
    expect(screen.getByText('Kp7#mQ9wTz4!aB')).toBeInTheDocument()
    expect(screen.getAllByText('samson@colton.example.com').length).toBeGreaterThan(0)
    expect(screen.getByText(/shown once and cannot be retrieved/i)).toBeInTheDocument()
  })

  it('hides the password once the admin says it is saved', async () => {
    await createAccount()

    fireEvent.click(screen.getByRole('button', { name: /i have saved it/i }))

    expect(screen.queryByText('Kp7#mQ9wTz4!aB')).not.toBeInTheDocument()
  })

  it('copies the login details', async () => {
    await createAccount()

    fireEvent.click(screen.getByRole('button', { name: /copy login details/i }))

    await waitFor(() => expect(writeText).toHaveBeenCalled())
    expect(writeText.mock.calls[0][0]).toContain('Temporary password: Kp7#mQ9wTz4!aB')
    expect(writeText.mock.calls[0][0]).toContain('Email: samson@colton.example.com')
  })

  it('tells the admin to copy by hand when the browser refuses the clipboard', async () => {
    writeText.mockRejectedValue(new Error('denied'))
    await createAccount()

    fireEvent.click(screen.getByRole('button', { name: /copy login details/i }))

    expect(await screen.findByText(/copy failed/i)).toBeInTheDocument()
  })

  it('goes straight on to adding jobs for the new client', async () => {
    await createAccount()

    expect(screen.getByText('Colton Group', { selector: 'p' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create draft job/i })).toBeInTheDocument()
  })

  it('sends a phone number when one is given', async () => {
    api.post.mockResolvedValueOnce({ data: PROVISIONED })
    render(<AdminClientsPage />)

    fillAccount({ 'Phone number (optional)': '+2348031234567' })
    await screen.findByText(/Account created/)

    expect(api.post.mock.calls[0][1].phone_number).toBe('+2348031234567')
  })

  it('shows the server message when the email is already taken', async () => {
    api.post.mockRejectedValueOnce({
      response: { status: 409, data: { message: 'A user with this email already exists' } },
    })
    render(<AdminClientsPage />)

    fillAccount()

    expect(await screen.findByRole('alert')).toHaveTextContent('A user with this email already exists')
    expect(screen.queryByText(/Account created/)).not.toBeInTheDocument()
  })

  it('checks the form before asking the server', async () => {
    render(<AdminClientsPage />)

    fillAccount({ 'Company name': '', 'Email address': 'not-an-email' })

    expect(await screen.findByText('Company name is required')).toBeInTheDocument()
    expect(screen.getByText('Enter a valid email address')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('refuses a name longer than the 30 characters the database holds', async () => {
    render(<AdminClientsPage />)

    fillAccount({ 'First name': 'A'.repeat(31) })

    expect(await screen.findByText('At most 30 characters')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('refuses a phone number that is not international', async () => {
    render(<AdminClientsPage />)

    fillAccount({ 'Phone number (optional)': '08031234567' })

    expect(await screen.findByText(/international format/i)).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })
})

describe('AdminClientsPage: interview jobs', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('says plainly that the client writes the interview brief', () => {
    render(<AdminClientsPage />)

    expect(screen.getByText(/client writes the AI interview brief themselves/i)).toBeInTheDocument()
  })

  it('creates a draft job inside the new client account and lists it', async () => {
    await createAccount()
    api.post.mockResolvedValueOnce({ data: { id: 'j-1', title: 'National Sales Manager' } })

    fillJob()

    expect(await screen.findByText('Draft, no interview brief yet')).toBeInTheDocument()
    expect(api.post).toHaveBeenLastCalledWith('/api/v1/admin/employers/u-1/jobs', {
      title: 'National Sales Manager',
      location: 'Lagos, Nigeria',
      contract_type: 'FULL_TIME',
      work_location: 'LOCAL',
      about_the_role: 'Lead national sales for an FMCG brand.',
      key_responsibilities: 'Own the national sales plan and distributors.',
      requirements: 'Twelve years of progressive FMCG sales experience.',
    })
  })

  it('clears the role but keeps the shared fields, ready for the next one', async () => {
    await createAccount()
    api.post.mockResolvedValueOnce({ data: { id: 'j-1', title: 'National Sales Manager' } })

    fillJob()
    await screen.findByText('Draft, no interview brief yet')

    expect(screen.getByLabelText('Job title')).toHaveValue('')
    expect(screen.getByLabelText('Location')).toHaveValue('Lagos, Nigeria')
  })

  it('shows the server message for a duplicate title', async () => {
    await createAccount()
    api.post.mockRejectedValueOnce({
      response: { status: 409, data: { message: 'This account already has a job with that title' } },
    })

    fillJob()

    expect(await screen.findByRole('alert')).toHaveTextContent('already has a job with that title')
  })

  it('checks the job form before asking the server', async () => {
    await createAccount()
    api.post.mockClear()

    fillJob({ 'Job title': 'ab', 'About the role': 'short' })

    expect(await screen.findByText('At least 3 characters')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('finds an existing client by search and adds the job to that account', async () => {
    api.get.mockResolvedValue({
      data: { items: [{ id: 'u-9', first_name: 'Ada', last_name: 'Eze', email: 'ada@acme.example.com' }] },
    })
    render(<AdminClientsPage />)

    type('Client', 'ada')
    fireEvent.click(await screen.findByRole('button', { name: /Ada Eze/ }))

    expect(api.get).toHaveBeenCalledWith('/api/v1/admin/users', {
      params: { role: 'EMPLOYER', search: 'ada', limit: 8 },
    })
    api.post.mockResolvedValueOnce({ data: { id: 'j-2', title: 'Finance Manager' } })
    fillJob({ 'Job title': 'Finance Manager' })

    await screen.findByText('Draft, no interview brief yet')
    expect(api.post).toHaveBeenLastCalledWith(
      '/api/v1/admin/employers/u-9/jobs',
      expect.objectContaining({ title: 'Finance Manager' })
    )
  })

  it('does not search for fewer than two characters', async () => {
    render(<AdminClientsPage />)

    type('Client', 'a')
    await new Promise((resolve) => setTimeout(resolve, 400))

    expect(api.get).not.toHaveBeenCalled()
  })
})
