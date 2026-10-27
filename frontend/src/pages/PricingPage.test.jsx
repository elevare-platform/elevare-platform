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

const COSTS = { introduction: 1, ai_interview: 10 }

function mockApi({ plans = PLANS, packs = PACKS, costs = COSTS } = {}) {
  api.get.mockImplementation((url) => {
    if (url.endsWith('/billing/plans')) return Promise.resolve({ data: plans })
    if (url.endsWith('/billing/credit-packages')) {
      return packs ? Promise.resolve({ data: packs }) : Promise.reject(new Error('down'))
    }
    if (url.endsWith('/billing/credit-costs')) {
      return costs ? Promise.resolve({ data: costs }) : Promise.reject(new Error('down'))
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

  it('says how many credits the paid plan includes each month and what they buy', async () => {
    mockApi()
    renderPricing()

    expect(
      await screen.findByText('40 credits included every month (about 4 interviews)')
    ).toBeInTheDocument()
  })

  it('states what an AI interview and an introduction cost, from the real price', async () => {
    mockApi({ costs: { introduction: 1, ai_interview: 12 } })
    renderPricing()

    expect(await screen.findByText('Interview: 12 credits.')).toBeInTheDocument()
    expect(screen.getByText('Introduction: 1 credit.')).toBeInTheDocument()
    expect(screen.getByText('40 credits included every month (about 3 interviews)')).toBeInTheDocument()
  })

  it('says how many AI interviews each pack buys', async () => {
    mockApi()
    renderPricing()

    expect(await screen.findByText('about 1 interview')).toBeInTheDocument()
    expect(screen.getByText('about 5 interviews')).toBeInTheDocument()
  })

  it('does not state an interview price when interviews are not charged for', async () => {
    mockApi({ costs: { introduction: 1, ai_interview: 0 } })
    renderPricing()

    await screen.findByText('40 credits included every month (introductions and interviews)')
    expect(screen.queryByText(/Interview: /)).not.toBeInTheDocument()
    expect(screen.queryByText(/about \d+ interview/)).not.toBeInTheDocument()
  })

  it('still shows the plans and packs when the costs cannot be loaded', async () => {
    mockApi({ costs: null })
    renderPricing()

    expect(
      await screen.findByText('40 credits included every month (introductions and interviews)')
    ).toBeInTheDocument()
    expect(screen.getByText('Need more credits?')).toBeInTheDocument()
    expect(screen.getByText('Introduction: 1 credit.')).toBeInTheDocument()
    expect(screen.queryByText(/Interview: /)).not.toBeInTheDocument()
  })

  it('shows no packs section when the packs cannot be loaded', async () => {
    mockApi({ packs: null })
    renderPricing()

    await screen.findByText('40 credits included every month (about 4 interviews)')
    expect(screen.queryByText('Need more credits?')).not.toBeInTheDocument()
  })
})
