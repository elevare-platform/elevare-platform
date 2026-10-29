import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), put: vi.fn() } }))

import api from '@/lib/api'
import ScorecardSummaryToggle from './ScorecardSummaryToggle'

const URL = '/api/v1/interviews/jobs/job-1/scorecard-summary'
const toggle = () => screen.getByRole('switch', { name: "Show the scorecard's Evaluation Summary" })

describe('ScorecardSummaryToggle', () => {
  beforeEach(() => vi.clearAllMocks())

  it('reads the job’s setting and shows it on', async () => {
    api.get.mockResolvedValueOnce({ data: { show_summary: true } })
    render(<ScorecardSummaryToggle jobId="job-1" />)

    await waitFor(() => expect(toggle()).toHaveAttribute('aria-checked', 'true'))
    expect(api.get).toHaveBeenCalledWith(URL)
    expect(screen.getByText(/On: the scorecard ends with its Evaluation Summary/)).toBeInTheDocument()
  })

  it('shows it off, and says where the section is gone, when it is switched off', async () => {
    api.get.mockResolvedValueOnce({ data: { show_summary: false } })
    render(<ScorecardSummaryToggle jobId="job-1" />)

    await waitFor(() => expect(toggle()).toHaveAttribute('aria-checked', 'false'))
    expect(screen.getByText(/Off: the scorecard has no Evaluation Summary/)).toBeInTheDocument()
  })

  it('cannot be pressed until the server has said how it stands', () => {
    api.get.mockReturnValueOnce(new Promise(() => {}))
    render(<ScorecardSummaryToggle jobId="job-1" />)

    expect(toggle()).toBeDisabled()
  })

  it('switches off and on again with a request each time', async () => {
    api.get.mockResolvedValueOnce({ data: { show_summary: true } })
    api.put.mockResolvedValueOnce({ data: { show_summary: false } })
    api.put.mockResolvedValueOnce({ data: { show_summary: true } })
    render(<ScorecardSummaryToggle jobId="job-1" />)
    await waitFor(() => expect(toggle()).toBeEnabled())

    fireEvent.click(toggle())
    await waitFor(() => expect(toggle()).toHaveAttribute('aria-checked', 'false'))
    expect(api.put).toHaveBeenLastCalledWith(URL, { show_summary: false })

    fireEvent.click(toggle())
    await waitFor(() => expect(toggle()).toHaveAttribute('aria-checked', 'true'))
    expect(api.put).toHaveBeenLastCalledWith(URL, { show_summary: true })
  })

  it('keeps the old setting and shows the server’s words when the change is refused', async () => {
    api.get.mockResolvedValueOnce({ data: { show_summary: true } })
    api.put.mockRejectedValueOnce({ response: { data: { message: 'Only an Elevare administrator can change this setting' } } })
    render(<ScorecardSummaryToggle jobId="job-1" />)
    await waitFor(() => expect(toggle()).toBeEnabled())

    fireEvent.click(toggle())

    expect(await screen.findByRole('alert')).toHaveTextContent('Only an Elevare administrator can change this setting')
    expect(toggle()).toHaveAttribute('aria-checked', 'true')
  })

  it('says it could not reach the server when there is no answer', async () => {
    api.get.mockResolvedValueOnce({ data: { show_summary: true } })
    api.put.mockRejectedValueOnce(new Error('Network Error'))
    render(<ScorecardSummaryToggle jobId="job-1" />)
    await waitFor(() => expect(toggle()).toBeEnabled())

    fireEvent.click(toggle())

    expect(await screen.findByRole('alert')).toHaveTextContent('We could not reach the server')
  })

  it('says it could not read the setting when the first request fails', async () => {
    api.get.mockRejectedValueOnce(new Error('boom'))
    render(<ScorecardSummaryToggle jobId="job-1" />)

    expect(await screen.findByText('We could not read this setting.')).toBeInTheDocument()
    expect(toggle()).toBeDisabled()
  })
})
