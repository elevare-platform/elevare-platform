import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

import api from '@/lib/api'
import InterviewDetailModal, { SCORE_POLL_INTERVAL_MS } from './InterviewDetailModal'

const BASE = {
  status: 'SCORED',
  transcript: 'AI: Hi\n\nCandidate: Hello',
  transcript_check: null,
  ai_score: null,
  ai_rationale: null,
  ai_scored_at: null,
  video_url: null,
  completed_at: '2026-10-14T10:00:00Z',
  cv_score: null,
  cv_strengths: null,
  cv_weaknesses: null,
  cv_fit_summary: null,
}

function renderModal() {
  render(
    <MemoryRouter>
      <InterviewDetailModal
        jobId="job-1"
        talentPoolProfileId="profile-1"
        candidateName="Ada"
        onClose={() => {}}
      />
    </MemoryRouter>
  )
}

const generateButton = () => screen.queryByRole('button', { name: /generate ai score/i })

async function advancePoll() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(SCORE_POLL_INTERVAL_MS)
  })
}

describe('InterviewDetailModal: scoring an interview that has no score', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    api.get.mockReset()
    api.post.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('offers a Generate AI score button when the finished interview has no score', async () => {
    api.get.mockResolvedValue({ data: BASE })
    renderModal()

    expect(await screen.findByRole('button', { name: /generate ai score/i })).toBeInTheDocument()
  })

  it('does not offer it when the interview already has a score', async () => {
    api.get.mockResolvedValue({ data: { ...BASE, ai_score: 82, ai_rationale: 'Strong answers.' } })
    renderModal()

    expect(await screen.findByText('Strong answers.')).toBeInTheDocument()
    expect(generateButton()).not.toBeInTheDocument()
  })

  it('says it is being scored, with no button, while scoring is already running', async () => {
    api.get.mockResolvedValue({ data: { ...BASE, status: 'UPLOADED' } })
    renderModal()

    expect(await screen.findByText(/scoring this interview/i)).toBeInTheDocument()
    expect(generateButton()).not.toBeInTheDocument()
  })

  it('keeps checking when opened mid-scoring, and shows the score without a click', async () => {
    api.get
      .mockResolvedValueOnce({ data: { ...BASE, status: 'UPLOADED' } }) // opening the window
      .mockResolvedValueOnce({ data: { ...BASE, status: 'UPLOADED' } }) // still running
      .mockResolvedValueOnce({
        data: { ...BASE, ai_score: 64, ai_rationale: 'Decent, with gaps.' },
      })
    renderModal()

    expect(await screen.findByText(/scoring this interview/i)).toBeInTheDocument()

    await advancePoll()
    expect(screen.getByText(/scoring this interview/i)).toBeInTheDocument()

    await advancePoll()
    expect(await screen.findByText('Decent, with gaps.')).toBeInTheDocument()
    expect(screen.queryByText(/scoring this interview/i)).not.toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('stops the spinner and offers a retry if scoring never finishes', async () => {
    api.get.mockResolvedValue({ data: { ...BASE, status: 'UPLOADED' } })
    renderModal()
    expect(await screen.findByText(/scoring this interview/i)).toBeInTheDocument()

    for (let i = 0; i < 40; i += 1) {
      await advancePoll()
    }

    expect(await screen.findByText(/taking longer than usual/i)).toBeInTheDocument()
    expect(screen.queryByText(/scoring this interview/i)).not.toBeInTheDocument()
    expect(generateButton()).toBeInTheDocument()
  })

  it('asks for scoring, waits, and shows the score when it arrives', async () => {
    api.post.mockResolvedValue({ data: { queued: true } })
    api.get
      .mockResolvedValueOnce({ data: BASE }) // opening the window
      .mockResolvedValueOnce({ data: { ...BASE, status: 'UPLOADED' } }) // still running
      .mockResolvedValueOnce({
        data: { ...BASE, ai_score: 77, ai_rationale: 'Clear and specific.' },
      })
    renderModal()

    fireEvent.click(await screen.findByRole('button', { name: /generate ai score/i }))

    expect(api.post).toHaveBeenCalledWith('/api/v1/interviews/score', null, {
      params: { job_id: 'job-1', talent_pool_profile_id: 'profile-1' },
    })
    expect(await screen.findByText(/scoring this interview/i)).toBeInTheDocument()

    await advancePoll() // sees it still running
    expect(screen.getByText(/scoring this interview/i)).toBeInTheDocument()

    await advancePoll() // sees the score
    expect(await screen.findByText('Clear and specific.')).toBeInTheDocument()
    expect(generateButton()).not.toBeInTheDocument()
  })

  it('points to an upgrade when the plan does not include scoring', async () => {
    api.get.mockResolvedValue({ data: BASE })
    api.post.mockRejectedValue({
      response: { data: { message: 'This feature requires a Professional plan or above' } },
    })
    renderModal()

    fireEvent.click(await screen.findByRole('button', { name: /generate ai score/i }))

    expect(
      await screen.findByText(/requires a professional plan or above/i)
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /upgrade plan/i })).toHaveAttribute('href', '/pricing')
    // The button is still there to try again after upgrading.
    expect(generateButton()).toBeInTheDocument()
  })

  it('says so when scoring finishes without producing a score, and lets them retry', async () => {
    api.post.mockResolvedValue({ data: { queued: true } })
    api.get
      .mockResolvedValueOnce({ data: BASE })
      .mockResolvedValueOnce({ data: BASE }) // finished again, still no score
    renderModal()

    fireEvent.click(await screen.findByRole('button', { name: /generate ai score/i }))
    await advancePoll()

    await waitFor(() =>
      expect(screen.getByText(/could not score this interview/i)).toBeInTheDocument()
    )
    expect(generateButton()).toBeInTheDocument()
  })
})
