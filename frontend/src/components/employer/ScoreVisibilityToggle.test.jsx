import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), put: vi.fn() } }))

import api from '@/lib/api'
import ScoreVisibilityToggle from './ScoreVisibilityToggle'

const URL = '/api/v1/interviews/jobs/job-1/score-visibility'
const toggle = () => screen.getByRole('switch', { name: 'Show interview scores and suggested bands' })

describe('ScoreVisibilityToggle', () => {
  beforeEach(() => vi.clearAllMocks())

  it('reads the job’s setting and shows it on', async () => {
    api.get.mockResolvedValueOnce({ data: { show_scores: true } })
    render(<ScoreVisibilityToggle jobId="job-1" />)

    await waitFor(() => expect(toggle()).toHaveAttribute('aria-checked', 'true'))
    expect(api.get).toHaveBeenCalledWith(URL)
    expect(screen.getByText(/On: the total score and the provisional band are shown/)).toBeInTheDocument()
  })

  it('shows it off, and says what is still shown, when the scores are switched off', async () => {
    api.get.mockResolvedValueOnce({ data: { show_scores: false } })
    render(<ScoreVisibilityToggle jobId="job-1" />)

    await waitFor(() => expect(toggle()).toHaveAttribute('aria-checked', 'false'))
    expect(screen.getByText(/Off: the total score and the provisional band are not shown/)).toBeInTheDocument()
    expect(screen.getByText(/The ratings and the evidence still are/)).toBeInTheDocument()
  })

  it('cannot be pressed until the server has said how it stands', () => {
    api.get.mockReturnValueOnce(new Promise(() => {}))
    render(<ScoreVisibilityToggle jobId="job-1" />)

    expect(toggle()).toBeDisabled()
  })

  it('switches off and on again with a request each time', async () => {
    api.get.mockResolvedValueOnce({ data: { show_scores: true } })
    api.put.mockResolvedValueOnce({ data: { show_scores: false } })
    api.put.mockResolvedValueOnce({ data: { show_scores: true } })
    render(<ScoreVisibilityToggle jobId="job-1" />)
    await waitFor(() => expect(toggle()).toBeEnabled())

    fireEvent.click(toggle())
    await waitFor(() => expect(toggle()).toHaveAttribute('aria-checked', 'false'))
    expect(api.put).toHaveBeenLastCalledWith(URL, { show_scores: false })

    fireEvent.click(toggle())
    await waitFor(() => expect(toggle()).toHaveAttribute('aria-checked', 'true'))
    expect(api.put).toHaveBeenLastCalledWith(URL, { show_scores: true })
  })

  it('keeps the old setting and shows the server’s words when the change is refused', async () => {
    api.get.mockResolvedValueOnce({ data: { show_scores: true } })
    api.put.mockRejectedValueOnce({ response: { data: { message: 'You do not have access to this job' } } })
    render(<ScoreVisibilityToggle jobId="job-1" />)
    await waitFor(() => expect(toggle()).toBeEnabled())

    fireEvent.click(toggle())

    expect(await screen.findByRole('alert')).toHaveTextContent('You do not have access to this job')
    expect(toggle()).toHaveAttribute('aria-checked', 'true')
  })

  it('says the server could not be reached when a change gets no answer', async () => {
    api.get.mockResolvedValueOnce({ data: { show_scores: true } })
    api.put.mockRejectedValueOnce(new Error('network'))
    render(<ScoreVisibilityToggle jobId="job-1" />)
    await waitFor(() => expect(toggle()).toBeEnabled())

    fireEvent.click(toggle())

    expect(await screen.findByRole('alert')).toHaveTextContent('We could not reach the server')
  })

  it('says the setting could not be read, and leaves the switch alone, when the first request fails', async () => {
    api.get.mockRejectedValueOnce(new Error('network'))
    render(<ScoreVisibilityToggle jobId="job-1" />)

    expect(await screen.findByText('We could not read this setting.')).toBeInTheDocument()
    expect(toggle()).toBeDisabled()
  })
})
