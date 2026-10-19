import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { HelmetProvider } from 'react-helmet-async'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn() } }))
vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({ user: null, logout: vi.fn(), authReady: true }),
  getPostAuthRedirect: vi.fn(),
}))

import api from '@/lib/api'
import PricingPage from './PricingPage'

const PLANS = [
  { name: 'Starter', price_kobo: 0, interval: 'MONTHLY', included_credits: null },
  { name: 'Professional', price_kobo: 4_500_000, interval: 'MONTHLY', included_credits: 40 },
  { name: 'Enterprise', price_kobo: 0, interval: 'MONTHLY', included_credits: null },
]
const PACKS = [
  { code: 'p10', name: 'Starter Pack', credits: 10, price_kobo: 1_500_000, currency: 'NGN' },
  { code: 'p50', name: 'Growth Pack', credits: 50, price_kobo: 6_500_000, currency: 'NGN' },
]

function mockApi({ plans = PLANS, packs = PACKS } = {}) {
  api.get.mockImplementation((url) => {
    if (url.endsWith('/billing/plans')) return Promise.resolve({ data: plans })
    if (url.endsWith('/billing/credit-packages')) {
      return packs ? Promise.resolve({ data: packs }) : Promise.reject(new Error('down'))
    }
    return Promise.reject(new Error(`unexpected ${url}`))
  })
}

function renderPricing() {
  return render(
    <HelmetProvider>
      <MemoryRouter>
        <PricingPage />
      </MemoryRouter>
    </HelmetProvider>
  )
}

describe('PricingPage credits', () => {
  beforeEach(() => vi.clearAllMocks())

  it('lists the credit packs with their price per credit', async () => {
    mockApi()
    renderPricing()

    expect(await screen.findByText('Need more credits?')).toBeInTheDocument()
    expect(screen.getByText('10 credits')).toBeInTheDocument()
    expect(screen.getByText('₦15,000')).toBeInTheDocument()
    expect(screen.getByText('₦1,500 per credit')).toBeInTheDocument()
    expect(screen.getByText('50 credits')).toBeInTheDocument()
    expect(screen.getByText('₦1,300 per credit')).toBeInTheDocument()
    expect(screen.getByText(/never expire/i, { selector: 'p.text-center' })).toBeInTheDocument()
  })

  it('says how many credits the paid plan includes each month, from the plan itself', async () => {
    mockApi()
    renderPricing()

    expect(
      await screen.findByText('40 credits included every month (introductions and AI interviews)')
    ).toBeInTheDocument()
  })

  it('shows no packs section when the packs cannot be loaded', async () => {
    mockApi({ packs: null })
    renderPricing()

    await screen.findByText('40 credits included every month (introductions and AI interviews)')
    expect(screen.queryByText('Need more credits?')).not.toBeInTheDocument()
  })
})
