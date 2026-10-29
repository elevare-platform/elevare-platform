import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), put: vi.fn() } }))

import api from '@/lib/api'
import ResultDisplayToggles from './ResultDisplayToggles'

const URL = '/api/v1/interviews/jobs/job-1/result-display'
const ALL_ON = { show_score_number: true, show_gaps: true, show_writeup: true }
const score = () => screen.getByRole('switch', { name: 'Show the score number' })
const gaps = () => screen.getByRole('switch', { name: 'Show the gaps and risks' })
const writeup = () => screen.getByRole('switch', { name: 'Show the written assessment' })

describe('ResultDisplayToggles', () => {
  beforeEach(() => vi.clearAllMocks())

  it('reads the job’s three settings and shows each as the server says', async () => {
    api.get.mockResolvedValueOnce({ data: { show_score_number: false, show_gaps: true, show_writeup: false } })
    render(<ResultDisplayToggles jobId="job-1" />)

    await waitFor(() => expect(score()).toHaveAttribute('aria-checked', 'false'))
    expect(api.get).toHaveBeenCalledWith(URL)
    expect(gaps()).toHaveAttribute('aria-checked', 'true')
    expect(writeup()).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByText(/no total, no points and no cut-offs. The suggested band and the 1 to 5 ratings are still shown/)).toBeInTheDocument()
    expect(screen.getByText(/The band, ratings and scorecard are still shown/)).toBeInTheDocument()
  })

  it('cannot be pressed until the server has said how they stand', () => {
    api.get.mockReturnValueOnce(new Promise(() => {}))
    render(<ResultDisplayToggles jobId="job-1" />)

    expect(score()).toBeDisabled()
    expect(gaps()).toBeDisabled()
    expect(writeup()).toBeDisabled()
  })

  it('changes only the switch that was pressed, sending only that field', async () => {
    api.get.mockResolvedValueOnce({ data: ALL_ON })
    api.put.mockResolvedValueOnce({ data: { ...ALL_ON, show_gaps: false } })
    render(<ResultDisplayToggles jobId="job-1" />)
    await waitFor(() => expect(gaps()).toBeEnabled())

    fireEvent.click(gaps())

    await waitFor(() => expect(gaps()).toHaveAttribute('aria-checked', 'false'))
    expect(api.put).toHaveBeenCalledWith(URL, { show_gaps: false })
    expect(score()).toHaveAttribute('aria-checked', 'true')
    expect(writeup()).toHaveAttribute('aria-checked', 'true')
  })

  it('switches off and on again with a request each time', async () => {
    api.get.mockResolvedValueOnce({ data: ALL_ON })
    api.put.mockResolvedValueOnce({ data: { ...ALL_ON, show_writeup: false } })
    api.put.mockResolvedValueOnce({ data: ALL_ON })
    render(<ResultDisplayToggles jobId="job-1" />)
    await waitFor(() => expect(writeup()).toBeEnabled())

    fireEvent.click(writeup())
    await waitFor(() => expect(writeup()).toHaveAttribute('aria-checked', 'false'))
    fireEvent.click(writeup())
    await waitFor(() => expect(writeup()).toHaveAttribute('aria-checked', 'true'))

    expect(api.put).toHaveBeenNthCalledWith(1, URL, { show_writeup: false })
    expect(api.put).toHaveBeenNthCalledWith(2, URL, { show_writeup: true })
  })

  it('keeps the old setting and shows the server’s words when the change is refused', async () => {
    api.get.mockResolvedValueOnce({ data: ALL_ON })
    api.put.mockRejectedValueOnce({ response: { data: { message: 'Only an Elevare administrator can change this setting' } } })
    render(<ResultDisplayToggles jobId="job-1" />)
    await waitFor(() => expect(score()).toBeEnabled())

    fireEvent.click(score())

    expect(await screen.findByRole('alert')).toHaveTextContent('Only an Elevare administrator can change this setting')
    expect(score()).toHaveAttribute('aria-checked', 'true')
  })

  it('says it could not reach the server, and could not read the settings', async () => {
    api.get.mockRejectedValueOnce(new Error('boom'))
    const { unmount } = render(<ResultDisplayToggles jobId="job-1" />)
    expect(await screen.findByText('We could not read these settings.')).toBeInTheDocument()
    unmount()

    api.get.mockResolvedValueOnce({ data: ALL_ON })
    api.put.mockRejectedValueOnce(new Error('Network Error'))
    render(<ResultDisplayToggles jobId="job-1" />)
    await waitFor(() => expect(score()).toBeEnabled())
    fireEvent.click(score())
    expect(await screen.findByRole('alert')).toHaveTextContent('We could not reach the server')
  })
})
