import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))

const AUTH = { user: { role: 'EMPLOYER' } }
vi.mock('@/context/AuthContext', () => ({ useAuth: () => AUTH }))

vi.mock('@/components/layout/Navbar', () => ({ default: () => null }))
vi.mock('@/components/layout/Footer', () => ({ default: () => null }))
vi.mock('@/components/candidates/CandidateProfilePanel', () => ({ default: () => null }))
vi.mock('@/components/employer/SourcedCvModal', () => ({ default: () => null }))
vi.mock('@/components/employer/CandidateActionModal', () => ({ default: () => null }))

import api from '@/lib/api'
import TalentPoolPage from './TalentPoolPage'

const base = {
  source: 'other',
  status: 'new',
  ownership: 'own_sourced',
  has_cv_access: true,
  candidate_current_title: 'Accountant',
  created_at: '2026-10-20T10:00:00Z',
  summary: 'Ten years in audit.',
  skills: ['Excel'],
}
const FRESH = { ...base, id: 'p-new', candidate_name: 'Ada Fresh', is_new: true }
const OLD = { ...base, id: 'p-old', candidate_name: 'Bola Older', is_new: false }

function serve({ items = [FRESH, OLD], count = 1, onlyNewItems = [FRESH] } = {}) {
  api.get.mockImplementation(async (url, config) => {
    if (url === '/api/v1/jobs/mine') return { data: { items: [] } }
    if (url === '/api/v1/talent-pool/new-count') return { data: { count } }
    if (url === '/api/v1/talent-pool') {
      return { data: { items: config?.params?.unseen ? onlyNewItems : items, next_cursor: null } }
    }
    return { data: {} }
  })
  api.post.mockResolvedValue({ data: { seen: true } })
}

const rowOf = (name) => screen.getByText(name).closest('div[class*="rounded-xl"]')

async function renderPage() {
  render(
    <MemoryRouter>
      <TalentPoolPage />
    </MemoryRouter>
  )
  await screen.findByText('Ada Fresh')
}

describe('TalentPoolPage, new CVs', () => {
  beforeEach(() => vi.clearAllMocks())

  it('marks a CV that has not been opened with New, and one that has with nothing', async () => {
    serve()
    await renderPage()

    expect(screen.getAllByTestId('new-badge')).toHaveLength(1)
    expect(within(rowOf('Ada Fresh')).getByTestId('new-badge')).toBeInTheDocument()
    expect(within(rowOf('Bola Older')).queryByTestId('new-badge')).not.toBeInTheDocument()
  })

  it('suggests looking at the new ones, with how many there are', async () => {
    serve({ count: 3 })
    await renderPage()

    expect(await screen.findByTestId('new-cvs-banner')).toHaveTextContent('3 new CVs you have not opened yet.')
  })

  it('says "1 new CV" for one', async () => {
    serve({ count: 1 })
    await renderPage()

    expect(await screen.findByTestId('new-cvs-banner')).toHaveTextContent('1 new CV you have not opened yet.')
  })

  it('shows no banner when nothing is new', async () => {
    serve({ items: [{ ...FRESH, is_new: false }, OLD], count: 0 })
    await renderPage()

    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/v1/talent-pool/new-count'))
    expect(screen.queryByTestId('new-cvs-banner')).not.toBeInTheDocument()
  })

  it('shows only the new ones when asked, asks the server for just those, and can go back', async () => {
    serve()
    await renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Show new only' }))

    await waitFor(() => expect(screen.queryByText('Bola Older')).not.toBeInTheDocument())
    expect(screen.getByTestId('new-cvs-banner')).toHaveTextContent('Showing only the CVs you have not opened yet.')
    const listCalls = api.get.mock.calls.filter(([url]) => url === '/api/v1/talent-pool')
    expect(listCalls.at(-1)[1].params.unseen).toBe(true)

    fireEvent.click(screen.getByRole('button', { name: 'Show all CVs' }))
    expect(await screen.findByText('Bola Older')).toBeInTheDocument()
    expect(api.get.mock.calls.filter(([url]) => url === '/api/v1/talent-pool').at(-1)[1].params.unseen).toBeUndefined()
  })

  it('stops being new the moment its CV is opened, lowers the count, and tells the server once', async () => {
    serve({ count: 1 })
    await renderPage()
    const row = screen.getByText('Ada Fresh').closest('div[class*="rounded-xl"]')

    fireEvent.click(within(row).getByTitle('View CV'))

    await waitFor(() => expect(screen.queryByTestId('new-badge')).not.toBeInTheDocument())
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(api.post).toHaveBeenCalledWith('/api/v1/talent-pool/p-new/seen')
    await waitFor(() => expect(screen.queryByTestId('new-cvs-banner')).not.toBeInTheDocument())
  })

  it('does not tell the server when a CV that is not new is opened', async () => {
    serve()
    await renderPage()
    const row = screen.getByText('Bola Older').closest('div[class*="rounded-xl"]')

    fireEvent.click(within(row).getByTitle('View CV'))

    expect(api.post).not.toHaveBeenCalled()
  })

  it('counts opening the details as having looked at it too', async () => {
    serve({ count: 1 })
    await renderPage()
    const row = screen.getByText('Ada Fresh').closest('div[class*="rounded-xl"]')

    fireEvent.click(within(row).getByLabelText('Show details'))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/v1/talent-pool/p-new/seen'))
  })

  it('does not count asking for an introduction as having looked at it', async () => {
    serve({ items: [{ ...FRESH, ownership: 'admin_sourced', has_cv_access: false }, OLD] })
    await renderPage()
    const row = screen.getByText('Ada Fresh').closest('div[class*="rounded-xl"]')

    fireEvent.click(within(row).getByTitle('Request Introduction'))

    expect(api.post).not.toHaveBeenCalled()
    expect(screen.getAllByTestId('new-badge')).toHaveLength(1)
  })

  it('works with a server that has no markers yet (no is_new, no count)', async () => {
    api.get.mockImplementation(async (url) => {
      if (url === '/api/v1/jobs/mine') return { data: { items: [] } }
      if (url === '/api/v1/talent-pool/new-count') throw new Error('404')
      return { data: { items: [{ ...OLD, candidate_name: 'Ada Fresh', is_new: undefined }], next_cursor: null } }
    })
    await renderPage()

    expect(screen.queryByTestId('new-badge')).not.toBeInTheDocument()
    expect(screen.queryByTestId('new-cvs-banner')).not.toBeInTheDocument()
  })
})
