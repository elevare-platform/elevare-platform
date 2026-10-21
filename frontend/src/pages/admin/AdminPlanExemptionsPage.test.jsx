import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }))
vi.mock('@/components/admin/AdminLayout', () => ({
  default: ({ children }) => <div>{children}</div>,
}))

import api from '@/lib/api'
import AdminPlanExemptionsPage from './AdminPlanExemptionsPage'

const URL = '/api/v1/admin/plan-exemptions'

function item(overrides = {}) {
  return {
    organization_id: 'org-1',
    company_name: 'Acme Ltd',
    reason: 'Pilot customer',
    granted_by: 'admin-1',
    expires_at: null,
    created_at: '2026-10-01T10:00:00Z',
    is_active: true,
    ...overrides,
  }
}

function page(items, total = items.length) {
  return { data: { items, total, limit: 20, offset: 0 } }
}

function type(label, value) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

function fillAndAdd({ email = 'ada@acme.example.com', reason = 'Pilot customer', endsOn } = {}) {
  type('Email of a team member', email)
  type('Reason', reason)
  if (endsOn) type('Ends on (optional)', endsOn)
  fireEvent.click(screen.getByRole('button', { name: /add company/i }))
}

describe('AdminPlanExemptionsPage: the list', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('asks for the first page and shows each company with its status and end date', async () => {
    api.get.mockResolvedValueOnce(
      page([
        item(),
        item({
          organization_id: 'org-2',
          company_name: 'Beta Ltd',
          reason: 'Demo account',
          expires_at: '2026-08-01T22:59:59Z',
          is_active: false,
        }),
      ])
    )

    render(<AdminPlanExemptionsPage />)

    expect(await screen.findByText('Acme Ltd')).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith(URL, { params: { limit: 20, offset: 0 } })
    expect(screen.getByText('Pilot customer')).toBeInTheDocument()
    expect(screen.getByText('Never')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Ended')).toBeInTheDocument()
    expect(screen.getByText('Showing 1 to 2 of 2')).toBeInTheDocument()
  })

  it('says so when no company is listed', async () => {
    api.get.mockResolvedValueOnce(page([]))

    render(<AdminPlanExemptionsPage />)

    expect(await screen.findByText('No company is on the list yet.')).toBeInTheDocument()
  })

  it('shows a message and can try again when the list fails to load', async () => {
    api.get.mockRejectedValueOnce(new Error('network'))
    api.get.mockResolvedValueOnce(page([item()]))

    render(<AdminPlanExemptionsPage />)

    expect(await screen.findByText('The list could not be loaded.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(await screen.findByText('Acme Ltd')).toBeInTheDocument()
  })

  it('pages forward and back by 20', async () => {
    api.get.mockResolvedValueOnce(page(Array.from({ length: 20 }, (_, i) => item({ organization_id: `a${i}`, company_name: `First ${i}` })), 45))
    api.get.mockResolvedValueOnce(page(Array.from({ length: 20 }, (_, i) => item({ organization_id: `b${i}`, company_name: `Second ${i}` })), 45))
    api.get.mockResolvedValueOnce(page([item({ organization_id: 'a0', company_name: 'First 0' })], 45))

    render(<AdminPlanExemptionsPage />)
    await screen.findByText('First 0')
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    await screen.findByText('Second 0')
    expect(api.get).toHaveBeenLastCalledWith(URL, { params: { limit: 20, offset: 20 } })

    fireEvent.click(screen.getByRole('button', { name: 'Previous' }))
    await screen.findByText('First 0')
    expect(api.get).toHaveBeenLastCalledWith(URL, { params: { limit: 20, offset: 0 } })
  })

  it('steps back a page when the page it was on has become empty', async () => {
    api.get.mockResolvedValueOnce(page(Array.from({ length: 20 }, (_, i) => item({ organization_id: `a${i}`, company_name: `First ${i}` })), 21))
    api.get.mockResolvedValueOnce(page([], 20)) // page 2 emptied by a removal elsewhere
    api.get.mockResolvedValueOnce(page(Array.from({ length: 20 }, (_, i) => item({ organization_id: `a${i}`, company_name: `First ${i}` })), 20))

    render(<AdminPlanExemptionsPage />)
    await screen.findByText('First 0')
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() =>
      expect(api.get).toHaveBeenLastCalledWith(URL, { params: { limit: 20, offset: 0 } })
    )
    expect(await screen.findByText('First 0')).toBeInTheDocument()
  })
})

describe('AdminPlanExemptionsPage: adding a company', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockResolvedValue(page([]))
  })

  it('sends the email, the reason and the end of the chosen day, then reloads the list', async () => {
    api.post.mockResolvedValueOnce({ data: item() })
    render(<AdminPlanExemptionsPage />)
    await screen.findByText('No company is on the list yet.')

    fillAndAdd({ endsOn: '2030-01-31' })

    expect(await screen.findByText('Acme Ltd now keeps Professional access.')).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledWith(URL, {
      email: 'ada@acme.example.com',
      reason: 'Pilot customer',
      expires_at: new Date('2030-01-31T23:59:59').toISOString(),
    })
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2))
  })

  it('leaves out the end date when none is chosen', async () => {
    api.post.mockResolvedValueOnce({ data: item() })
    render(<AdminPlanExemptionsPage />)
    await screen.findByText('No company is on the list yet.')

    fillAndAdd()

    await screen.findByText('Acme Ltd now keeps Professional access.')
    expect(api.post).toHaveBeenCalledWith(URL, {
      email: 'ada@acme.example.com',
      reason: 'Pilot customer',
    })
  })

  it('checks the form before sending anything', async () => {
    render(<AdminPlanExemptionsPage />)
    await screen.findByText('No company is on the list yet.')

    fillAndAdd({ email: 'not-an-email', reason: 'ab' })

    expect(await screen.findByText('Enter a valid email address')).toBeInTheDocument()
    expect(screen.getByText('Give a reason of at least 3 characters')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it("shows the server's own message, for example an unknown email", async () => {
    api.post.mockRejectedValueOnce({
      response: { status: 404, data: { code: 'USER_NOT_FOUND', message: 'No account has that email address' } },
    })
    render(<AdminPlanExemptionsPage />)
    await screen.findByText('No company is on the list yet.')

    fillAndAdd()

    expect(await screen.findByRole('alert')).toHaveTextContent('No account has that email address')
  })

  it('shows the first problem the server found in the form', async () => {
    api.post.mockRejectedValueOnce({
      response: {
        status: 422,
        data: { code: 'VALIDATION_ERROR', details: [{ field: 'expires_at', message: 'The end date must be in the future' }] },
      },
    })
    render(<AdminPlanExemptionsPage />)
    await screen.findByText('No company is on the list yet.')

    fillAndAdd({ endsOn: '2030-01-31' })

    expect(await screen.findByRole('alert')).toHaveTextContent('The end date must be in the future')
  })

  it('falls back to a general message when the server sent none', async () => {
    api.post.mockRejectedValueOnce(new Error('network'))
    render(<AdminPlanExemptionsPage />)
    await screen.findByText('No company is on the list yet.')

    fillAndAdd()

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong. Please try again.')
  })
})

describe('AdminPlanExemptionsPage: removing a company', () => {
  let confirmSpy

  beforeEach(() => {
    vi.clearAllMocks()
    confirmSpy = vi.spyOn(window, 'confirm')
  })

  afterEach(() => {
    confirmSpy.mockRestore()
  })

  it('asks first, then removes the company and reloads the list', async () => {
    confirmSpy.mockReturnValue(true)
    api.get.mockResolvedValueOnce(page([item()]))
    api.get.mockResolvedValueOnce(page([]))
    api.delete.mockResolvedValueOnce({})
    render(<AdminPlanExemptionsPage />)
    await screen.findByText('Acme Ltd')

    fireEvent.click(screen.getByRole('button', { name: 'Remove Acme Ltd' }))

    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('Acme Ltd'))
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith(`${URL}/org-1`))
    expect(await screen.findByText('No company is on the list yet.')).toBeInTheDocument()
  })

  it('does nothing when the admin says no', async () => {
    confirmSpy.mockReturnValue(false)
    api.get.mockResolvedValueOnce(page([item()]))
    render(<AdminPlanExemptionsPage />)
    await screen.findByText('Acme Ltd')

    fireEvent.click(screen.getByRole('button', { name: 'Remove Acme Ltd' }))

    expect(api.delete).not.toHaveBeenCalled()
    expect(screen.getByText('Acme Ltd')).toBeInTheDocument()
  })

  it('tells the admin when the removal fails and keeps the company listed', async () => {
    confirmSpy.mockReturnValue(true)
    api.get.mockResolvedValueOnce(page([item()]))
    api.delete.mockRejectedValueOnce({
      response: { status: 404, data: { code: 'PLAN_EXEMPTION_NOT_FOUND', message: 'That company is not on the exemption list' } },
    })
    render(<AdminPlanExemptionsPage />)
    await screen.findByText('Acme Ltd')

    fireEvent.click(screen.getByRole('button', { name: 'Remove Acme Ltd' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('That company is not on the exemption list')
    expect(screen.getByText('Acme Ltd')).toBeInTheDocument()
  })
})
