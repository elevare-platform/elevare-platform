import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn() } }))

import api from '@/lib/api'
import SharedApplicantsPage from './SharedApplicantsPage'

const daysAgo = (n) => new Date(Date.now() - n * 86_400_000).toISOString()

function applicant(overrides) {
  return {
    initials: 'AB',
    full_name: null,
    ai_score: 80,
    ai_fit_summary: null,
    ai_strengths: null,
    ai_weaknesses: null,
    cv_snippet: null,
    cv_download_url: null,
    source: 'applicant',
    created_at: daysAgo(3),
    ai_score_computed_at: daysAgo(1),
    ...overrides,
  }
}

function renderShared() {
  return render(
    <MemoryRouter initialEntries={['/shared/jobs/tok-1']}>
      <Routes>
        <Route path="/shared/jobs/:token" element={<SharedApplicantsPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('SharedApplicantsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows when each candidate arrived, in score order, with a clear verb per source', async () => {
    api.get.mockResolvedValue({
      data: {
        job_title: 'Accountant',
        expires_at: daysAgo(-5),
        applicants: [
          applicant({ initials: 'JD', source: 'applicant', created_at: daysAgo(3) }),
          applicant({ initials: 'EX', source: 'external', ai_score: 60, created_at: daysAgo(40) }),
        ],
      },
    })
    renderShared()

    expect(await screen.findByText(/Applied 3d ago · Scored 1d ago/)).toBeInTheDocument()
    expect(screen.getByText('New')).toBeInTheDocument()
    expect(screen.getByText(/Added 1mo ago/).closest('p')).toHaveAttribute('data-age', 'stale')
  })

  it('still renders candidates from an older API that sends no dates', async () => {
    api.get.mockResolvedValue({
      data: {
        job_title: 'Accountant',
        expires_at: daysAgo(-5),
        applicants: [applicant({ initials: 'JD', created_at: undefined, ai_score_computed_at: undefined })],
      },
    })
    renderShared()

    expect(await screen.findByText('JD')).toBeInTheDocument()
    expect(screen.queryByText(/Applied|Added/)).not.toBeInTheDocument()
  })
})
