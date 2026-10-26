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

// ── A strict interview that ended early ─────────────────────────────────────

const STRICT = {
  rules_version: 'S2',
  rules_accepted_at: '2026-10-20T09:00:05Z',
  attempt: 1,
  ended: 'TOO_MANY_LEAVES',
  ended_at: '2026-10-20T09:07:00Z',
  leaves: 4,
  away_seconds: 20,
  key_presses: 0,
  reloads: 0,
  events: [{ kind: 'ENDED', detail: 'TOO_MANY_LEAVES', occurred_at: '2026-10-20T09:07:00Z', duration_seconds: null, attempt: 1, counted: false }],
  turns: [{ number: 1, kind: 'QUESTION', question: 'Tell us about a system.', answer: 'I built billing.', answered: true }],
}
const ENDED = { ...BASE, status: 'ENDED_CONDUCT', completed_at: '2026-10-20T09:08:00Z', strict: STRICT }

function renderEnded(props = {}) {
  const onReinstated = vi.fn()
  const onClose = vi.fn()
  render(
    <MemoryRouter>
      <InterviewDetailModal
        jobId="job-1"
        talentPoolProfileId="profile-1"
        candidateName="Ada"
        onClose={onClose}
        onReinstated={onReinstated}
        {...props}
      />
    </MemoryRouter>
  )
  return { onReinstated, onClose }
}

describe('InterviewDetailModal: an interview that ended early', () => {
  beforeEach(() => {
    api.get.mockReset()
    api.post.mockReset()
  })

  it('says it ended early and has not been scored, and shows the notes with it', async () => {
    api.get.mockResolvedValue({ data: ENDED })
    renderEnded()

    expect(await screen.findByText(/Ended early\. It has not been scored/)).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Interview notes' })).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent('left the interview screen too many times')
  })

  it('says it was the candidate who stopped it, when they did', async () => {
    api.get.mockResolvedValue({ data: { ...ENDED, status: 'STOPPED', strict: { ...STRICT, ended: 'STOPPED' } } })
    renderEnded()

    expect(await screen.findByText(/Stopped by the candidate\. It has not been scored/)).toBeInTheDocument()
  })

  it('reinstates it with the job and the candidate, tells the owner the candidate was emailed, and tells the list', async () => {
    api.get.mockResolvedValue({ data: ENDED })
    api.post.mockResolvedValue({ data: { status: 'PENDING', interview_url: 'https://x/i/t', email_sent: true } })
    const { onReinstated } = renderEnded()

    fireEvent.click(await screen.findByRole('button', { name: 'Reinstate this interview' }))

    expect(await screen.findByText('The interview was reinstated')).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledWith('/api/v1/interviews/profile-1/reinstate', null, { params: { job_id: 'job-1' } })
    expect(screen.getByText(/emailed the same link/)).toBeInTheDocument()
    expect(onReinstated).toHaveBeenCalledTimes(1)
  })

  it('tells the owner to send the link themselves when there is no email on file', async () => {
    api.get.mockResolvedValue({ data: ENDED })
    api.post.mockResolvedValue({ data: { status: 'PENDING', interview_url: 'https://x/i/t', email_sent: false } })
    renderEnded()

    fireEvent.click(await screen.findByRole('button', { name: 'Reinstate this interview' }))

    expect(await screen.findByText(/no email address on file/)).toBeInTheDocument()
  })

  it("shows the server's message when it cannot be reinstated, and keeps the button", async () => {
    api.get.mockResolvedValue({ data: ENDED })
    api.post.mockRejectedValue({
      response: { data: { message: 'The recording of this interview is still being prepared. Please try again in a minute.' } },
    })
    const { onReinstated } = renderEnded()

    fireEvent.click(await screen.findByRole('button', { name: 'Reinstate this interview' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('still being prepared')
    expect(screen.getByRole('button', { name: 'Reinstate this interview' })).toBeEnabled()
    expect(onReinstated).not.toHaveBeenCalled()
  })

  it('offers no reinstate button for an interview that finished', async () => {
    api.get.mockResolvedValue({ data: { ...BASE, strict: { ...STRICT, ended: null } } })
    renderEnded()

    await screen.findByRole('region', { name: 'Interview notes' })
    expect(screen.queryByRole('button', { name: 'Reinstate this interview' })).not.toBeInTheDocument()
  })

  it('says the recording is being put together, not that there is none, while the pieces are joined', async () => {
    api.get.mockResolvedValue({ data: { ...BASE, strict: { ...STRICT, ended: null, recording_pending: true } } })
    renderEnded()

    expect(await screen.findByText(/being put together/)).toBeInTheDocument()
    expect(screen.queryByText(/No recording is available/)).not.toBeInTheDocument()
  })

  it('warns that the video may be only part of the interview, next to the video', async () => {
    api.get.mockResolvedValue({
      data: { ...BASE, video_url: 'https://r2/v.webm', strict: { ...STRICT, ended: null, recording_partial: true } },
    })
    renderEnded()

    expect(await screen.findByText(/only part of this interview/)).toBeInTheDocument()
  })

  it('shows a reinstated interview as one clip per attempt', async () => {
    api.get.mockResolvedValue({
      data: {
        ...BASE,
        video_url: 'https://r2/two.webm',
        recordings: [
          { attempt: 1, video_url: 'https://r2/one.webm' },
          { attempt: 2, video_url: 'https://r2/two.webm' },
        ],
        strict: { ...STRICT, ended: null, attempt: 2 },
      },
    })
    renderEnded()

    expect(await screen.findByText('Attempt 1')).toBeInTheDocument()
    expect(screen.getByText('Attempt 2, after the interview was reinstated')).toBeInTheDocument()
    expect(document.querySelectorAll('video')).toHaveLength(2)
  })

  it('shows one plain player for an interview that was never reinstated', async () => {
    api.get.mockResolvedValue({
      data: { ...BASE, video_url: 'https://r2/v.webm', recordings: [{ attempt: 1, video_url: 'https://r2/v.webm' }] },
    })
    renderEnded()

    await screen.findByText(/Transcript/)
    expect(document.querySelectorAll('video')).toHaveLength(1)
    expect(screen.queryByText(/each attempt has its own recording/)).not.toBeInTheDocument()
  })

  it('shows the earlier clip, not "no recording", when the latest attempt recorded nothing new', async () => {
    api.get.mockResolvedValue({
      data: {
        ...BASE,
        video_url: null,
        recordings: [{ attempt: 1, video_url: 'https://r2/one.webm' }],
        strict: { ...STRICT, ended: null, attempt: 2 },
      },
    })
    renderEnded()

    expect(await screen.findByText('Attempt 1')).toBeInTheDocument()
    expect(screen.queryByText(/No recording is available/)).not.toBeInTheDocument()
  })

  it('shows the weighted table, not the single score card, for an interview scored with a profile', async () => {
    const report = {
      rows: [
        { name: 'Strategy', weight: 60, key: true, rating: 4 },
        { name: 'P&L', weight: 40, key: false, rating: 3 },
      ],
      points: 72, assessed_weight: 100, total_weight: 100, complete: true, score: 72, band: 'Hold for evidence',
      bands: { strong: 85, shortlist: 75, hold: 65 }, key_min_rating: 3, key_flags: [], unassessed: [],
    }
    api.get.mockResolvedValue({ data: { ...BASE, ai_score: 72, ai_rationale: 'A steady candidate.', score_report: report } })
    renderEnded()

    expect(await screen.findByTestId('weighted-total')).toHaveTextContent('72 / 100')
    expect(screen.getByTestId('weighted-band')).toHaveTextContent('Hold for evidence')
    expect(screen.getByText('A steady candidate.')).toBeInTheDocument()
  })

  it('shows an incomplete score as incomplete, not as "no AI score is available"', async () => {
    const report = {
      rows: [{ name: 'Strategy', weight: 60, key: true, rating: 4 }, { name: 'P&L', weight: 40, key: false, rating: null }],
      points: 48, assessed_weight: 60, total_weight: 100, complete: false, score: null, band: null,
      bands: { strong: 85, shortlist: 75, hold: 65 }, key_min_rating: 3, key_flags: [], unassessed: ['P&L'],
    }
    api.get.mockResolvedValue({ data: { ...BASE, status: 'SCORED', ai_score: null, ai_rationale: 'INCOMPLETE SCORE.', score_report: report } })
    renderEnded()

    expect(await screen.findByTestId('weighted-incomplete')).toBeInTheDocument()
    expect(screen.queryByText(/No AI score is available/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Generate AI score' })).not.toBeInTheDocument()
  })

  it('shows no notes for a live interview', async () => {
    api.get.mockResolvedValue({ data: { ...BASE, strict: null } })
    renderEnded()

    await screen.findByText(/Transcript/)
    expect(screen.queryByRole('region', { name: 'Interview notes' })).not.toBeInTheDocument()
  })

  it('asks before scoring what was recorded, because that closes the interview', async () => {
    api.get.mockResolvedValue({ data: ENDED })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderEnded()

    fireEvent.click(await screen.findByRole('button', { name: 'Score what was recorded' }))

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('can no longer carry on'))
    expect(api.post).not.toHaveBeenCalled()
    confirm.mockRestore()
  })

  it('scores what was recorded once the owner agrees', async () => {
    api.get.mockResolvedValue({ data: ENDED })
    api.post.mockResolvedValue({ data: { queued: true } })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderEnded()

    fireEvent.click(await screen.findByRole('button', { name: 'Score what was recorded' }))

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/api/v1/interviews/score', null, { params: { job_id: 'job-1', talent_pool_profile_id: 'profile-1' } })
    )
    confirm.mockRestore()
  })

  it('does not offer a score for an interview that has not finished or ended', async () => {
    api.get.mockResolvedValue({ data: ENDED })
    renderEnded()

    await screen.findByText(/Ended early/)
    expect(screen.queryByRole('button', { name: /generate ai score/i })).not.toBeInTheDocument()
  })
})
