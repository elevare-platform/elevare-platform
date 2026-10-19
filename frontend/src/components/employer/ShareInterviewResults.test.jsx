import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }))

import api from '@/lib/api'
import ShareInterviewResults from './ShareInterviewResults'

const URL = 'https://app.example/shared/interviews/tok123'
const LIVE = {
  url: URL,
  created_at: '2026-10-20T09:00:00Z',
  expires_at: '2099-10-23T09:00:00Z',
  expired: false,
  view_count: 0,
  last_viewed_at: null,
}
const ENDPOINT = '/api/v1/interview-share/jobs/job-1'

describe('ShareInterviewResults', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })
  afterEach(() => vi.restoreAllMocks())

  it('says what a link shows and how long it works, and offers to create one', async () => {
    api.get.mockResolvedValueOnce({ data: { link: null } })
    render(<ShareInterviewResults jobId="job-1" />)

    expect(await screen.findByRole('button', { name: 'Create link' })).toBeInTheDocument()
    expect(screen.getByText(/no login\. It works for 3 days/)).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith(ENDPOINT)
  })

  it('creates a link and shows it with when it expires', async () => {
    api.get.mockResolvedValueOnce({ data: { link: null } })
    api.post.mockResolvedValueOnce({ data: LIVE })
    render(<ShareInterviewResults jobId="job-1" />)

    fireEvent.click(await screen.findByRole('button', { name: 'Create link' }))

    expect(await screen.findByLabelText('Interview results link')).toHaveValue(URL)
    expect(api.post).toHaveBeenCalledWith(ENDPOINT)
    expect(screen.getByText(/Not opened yet/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Create link' })).not.toBeInTheDocument()
  })

  it('shows an existing link straight away, and how often it has been opened', async () => {
    api.get.mockResolvedValueOnce({
      data: { link: { ...LIVE, view_count: 2, last_viewed_at: '2026-10-21T10:00:00Z' } },
    })
    render(<ShareInterviewResults jobId="job-1" />)

    expect(await screen.findByLabelText('Interview results link')).toHaveValue(URL)
    expect(screen.getByText(/Opened 2 times/)).toBeInTheDocument()
  })

  it('copies the link', async () => {
    const writeText = vi.fn().mockResolvedValue()
    Object.assign(navigator, { clipboard: { writeText } })
    api.get.mockResolvedValueOnce({ data: { link: LIVE } })
    render(<ShareInterviewResults jobId="job-1" />)

    fireEvent.click(await screen.findByRole('button', { name: /Copy/ }))

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(URL))
    expect(await screen.findByText('Copied')).toBeInTheDocument()
  })

  it('makes a new link after asking, which replaces the old one', async () => {
    const fresh = { ...LIVE, url: 'https://app.example/shared/interviews/tok999' }
    api.get.mockResolvedValueOnce({ data: { link: LIVE } })
    api.post.mockResolvedValueOnce({ data: fresh })
    render(<ShareInterviewResults jobId="job-1" />)

    fireEvent.click(await screen.findByRole('button', { name: 'Make a new link' }))

    expect(window.confirm).toHaveBeenCalledWith(expect.stringMatching(/stops the current link/))
    await waitFor(() =>
      expect(screen.getByLabelText('Interview results link')).toHaveValue(fresh.url)
    )
  })

  it('does nothing when the person decides not to replace it', async () => {
    window.confirm.mockReturnValue(false)
    api.get.mockResolvedValueOnce({ data: { link: LIVE } })
    render(<ShareInterviewResults jobId="job-1" />)

    fireEvent.click(await screen.findByRole('button', { name: 'Make a new link' }))

    expect(api.post).not.toHaveBeenCalled()
  })

  it('stops sharing after asking', async () => {
    api.get.mockResolvedValueOnce({ data: { link: LIVE } })
    api.delete.mockResolvedValueOnce({})
    render(<ShareInterviewResults jobId="job-1" />)

    fireEvent.click(await screen.findByRole('button', { name: 'Stop sharing' }))

    expect(await screen.findByRole('button', { name: 'Create link' })).toBeInTheDocument()
    expect(api.delete).toHaveBeenCalledWith(ENDPOINT)
    expect(screen.queryByLabelText('Interview results link')).not.toBeInTheDocument()
  })

  it('says when the last link expired and offers a new one', async () => {
    api.get.mockResolvedValueOnce({ data: { link: { ...LIVE, expired: true } } })
    render(<ShareInterviewResults jobId="job-1" />)

    expect(await screen.findByText(/The last link expired on/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Make a new link' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Interview results link')).not.toBeInTheDocument()
  })

  it('says so when a link cannot be made, and keeps what it had', async () => {
    api.get.mockResolvedValueOnce({ data: { link: null } })
    api.post.mockRejectedValueOnce({ response: { data: { message: 'You do not have access to this job' } } })
    render(<ShareInterviewResults jobId="job-1" />)

    fireEvent.click(await screen.findByRole('button', { name: 'Create link' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('You do not have access to this job')
    expect(screen.getByRole('button', { name: 'Create link' })).toBeInTheDocument()
  })

  it('says so when the link status cannot be loaded', async () => {
    api.get.mockRejectedValueOnce(new Error('network'))
    render(<ShareInterviewResults jobId="job-1" />)

    expect(await screen.findByRole('alert')).toHaveTextContent('could not check')
  })
})
