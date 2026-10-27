import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

import api from '@/lib/api'
import SharedApplicantsPage from './SharedApplicantsPage'

const daysAgo = (n) => new Date(Date.now() - n * 86_400_000).toISOString()

function candidate(key, over = {}) {
  return {
    initials: key.toUpperCase().slice(0, 2),
    full_name: null,
    ai_score: 80,
    ai_fit_summary: 'A steady fit for the role.',
    ai_strengths: ['Clear examples'],
    ai_weaknesses: null,
    cv_snippet: null,
    cv_download_url: null,
    source: 'external',
    created_at: daysAgo(3),
    ai_score_computed_at: daysAgo(3),
    item_key: key.padEnd(16, '0'),
    is_unseen: true,
    is_new_since_last_visit: false,
    ...over,
  }
}

function serve(over = {}, applicants = [candidate('aa'), candidate('bb')]) {
  const unseen = applicants.filter((a) => a.is_unseen).length
  const fresh = applicants.filter((a) => a.is_new_since_last_visit).length
  api.get.mockResolvedValue({
    data: {
      job_title: 'Accountant',
      expires_at: daysAgo(-5),
      applicants,
      unseen_count: unseen,
      new_since_last_visit_count: fresh,
      previous_visit_at: null,
      ...over,
    },
  })
  api.post.mockResolvedValue({ data: {} })
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

const tab = (name) => screen.getByRole('tab', { name })

describe('SharedApplicantsPage, what has been opened', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows a first visitor every candidate as not opened, with the count on the tab, and nothing as new', async () => {
    serve()
    renderShared()

    expect(await screen.findAllByTestId('unopened-badge')).toHaveLength(2)
    expect(tab('Not opened yet (2)')).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: /New since your last visit/ })).not.toBeInTheDocument()
    expect(screen.queryByTestId('new-since-badge')).not.toBeInTheDocument()
  })

  it('tells someone who is back what was added since their last visit, and offers a tab for only those', async () => {
    serve(
      { previous_visit_at: daysAgo(7) },
      [candidate('aa', { is_new_since_last_visit: true }), candidate('bb', { is_unseen: false })]
    )
    renderShared()

    expect(await screen.findByText(/1 new candidate has been added since your last visit on/)).toBeInTheDocument()
    expect(screen.getAllByTestId('new-since-badge')).toHaveLength(1)

    fireEvent.click(tab('New since your last visit (1)'))
    expect(screen.queryByText('BB')).not.toBeInTheDocument()
    expect(screen.getByText('AA')).toBeInTheDocument()
  })

  it('opening a candidate\'s details marks it opened at once, lowers the count, and tells the server once', async () => {
    serve()
    renderShared()
    await screen.findAllByTestId('unopened-badge')

    fireEvent.click(screen.getAllByLabelText('Expand details')[0])

    await waitFor(() => expect(screen.getAllByTestId('unopened-badge')).toHaveLength(1))
    expect(tab('Not opened yet (1)')).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(api.post).toHaveBeenCalledWith('/api/v1/public/jobs/tok-1/seen', { item_key: 'aa00000000000000' })
  })

  it('opening the CV counts too, and closing and reopening the details does not tell the server again', async () => {
    serve({}, [candidate('aa', { cv_download_url: 'https://r2/cv.pdf', ai_fit_summary: null, ai_strengths: null })])
    renderShared()
    await screen.findByTestId('unopened-badge')

    fireEvent.click(screen.getByLabelText('Download CV'))
    await waitFor(() => expect(screen.queryByTestId('unopened-badge')).not.toBeInTheDocument())
    fireEvent.click(screen.getByLabelText('Download CV'))

    expect(api.post).toHaveBeenCalledTimes(1)
  })

  it('shows only what has not been opened on that tab, and says so when everything has been', async () => {
    serve({}, [candidate('aa', { is_unseen: false }), candidate('bb')])
    renderShared()
    await screen.findByText('AA')

    fireEvent.click(tab('Not opened yet (1)'))
    expect(screen.queryByText('AA')).not.toBeInTheDocument()
    expect(screen.getByText('BB')).toBeInTheDocument()

    fireEvent.click(screen.getAllByLabelText('Expand details')[0])
    await waitFor(() => expect(screen.getByText('You have opened every candidate on this list.')).toBeInTheDocument())

    fireEvent.click(tab('All'))
    expect(screen.getByText('AA')).toBeInTheDocument()
  })

  it('does not tell the server about a candidate that was already opened', async () => {
    serve({}, [candidate('aa', { is_unseen: false })])
    renderShared()
    await screen.findByText('AA')

    fireEvent.click(screen.getByLabelText('Expand details'))

    expect(api.post).not.toHaveBeenCalled()
  })

  it('keeps working when the server tells it nothing about opened candidates (an older server)', async () => {
    api.get.mockResolvedValue({
      data: {
        job_title: 'Accountant',
        expires_at: daysAgo(-5),
        applicants: [{ ...candidate('aa'), item_key: undefined, is_unseen: undefined }],
      },
    })
    renderShared()

    expect(await screen.findByText('AA')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Expand details'))
    expect(api.post).not.toHaveBeenCalled()
    expect(screen.queryByTestId('unopened-badge')).not.toBeInTheDocument()
  })

  it('does not break the page when remembering the opened candidate fails', async () => {
    serve()
    api.post.mockRejectedValue(new Error('offline'))
    renderShared()
    await screen.findAllByTestId('unopened-badge')

    fireEvent.click(screen.getAllByLabelText('Expand details')[0])

    await waitFor(() => expect(screen.getAllByTestId('unopened-badge')).toHaveLength(1))
    expect(within(screen.getByTestId('seen-tabs')).getByRole('tab', { name: 'Not opened yet (1)' })).toBeInTheDocument()
  })
})
