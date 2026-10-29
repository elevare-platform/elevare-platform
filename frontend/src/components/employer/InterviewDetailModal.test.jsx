import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }))

import api from '@/lib/api'
import InterviewDetailModal, { RESCORE_POLL_INTERVAL_MS, SCORE_POLL_INTERVAL_MS } from './InterviewDetailModal'

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

const generateButton = () => screen.queryByRole('button', { name: /generate score/i })

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

    expect(await screen.findByRole('button', { name: /generate score/i })).toBeInTheDocument()
  })

  it('offers Retry scoring, not Generate score, when scoring failed after the recording arrived', async () => {
    api.get.mockResolvedValue({ data: { ...BASE, status: 'FAILED' } })
    renderModal()

    expect(await screen.findByRole('button', { name: 'Retry scoring' })).toBeInTheDocument()
    expect(generateButton()).not.toBeInTheDocument()
    expect(screen.getByText(/If its credit was given back, retrying uses one again/)).toBeInTheDocument()
  })

  it('retries with the same request as a first score, and waits for the result', async () => {
    api.get.mockResolvedValueOnce({ data: { ...BASE, status: 'FAILED' } })
    api.post.mockResolvedValueOnce({ data: { queued: true } })
    api.get.mockResolvedValue({ data: { ...BASE, status: 'SCORED', ai_score: 77, ai_rationale: 'Scored on the second try.' } })
    renderModal()

    fireEvent.click(await screen.findByRole('button', { name: 'Retry scoring' }))
    expect(api.post).toHaveBeenCalledWith('/api/v1/interviews/score', null, {
      params: { job_id: 'job-1', talent_pool_profile_id: 'profile-1' },
    })
    await advancePoll()

    expect(await screen.findByText('Scored on the second try.')).toBeInTheDocument()
  })

  it('shows the server’s words when the retry is refused, such as short of credits', async () => {
    api.get.mockResolvedValue({ data: { ...BASE, status: 'FAILED' } })
    api.post.mockRejectedValueOnce({ response: { data: { message: 'Not enough credits' } } })
    renderModal()

    fireEvent.click(await screen.findByRole('button', { name: 'Retry scoring' }))

    expect(await screen.findByText('Not enough credits')).toBeInTheDocument()
  })

  it('offers no scoring for an interview that failed before it was finished', async () => {
    api.get.mockResolvedValue({ data: { ...BASE, status: 'FAILED', completed_at: null } })
    renderModal()

    await screen.findByText(/No score is available/)
    expect(screen.queryByRole('button', { name: 'Retry scoring' })).not.toBeInTheDocument()
    expect(generateButton()).not.toBeInTheDocument()
  })

  it('shows the written assessment with no score, and not the empty-score message, when the job’s switch has scores off', async () => {
    api.get.mockResolvedValue({
      data: { ...BASE, ai_score: null, scores_hidden: true, ai_rationale: 'A steady candidate. Strong on strategy.' },
    })
    renderModal()

    expect(await screen.findByText('A steady candidate. Strong on strategy.')).toBeInTheDocument()
    expect(screen.queryByText(/No score is available/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /generate score/i })).not.toBeInTheDocument()
    expect(screen.queryByTestId('reviewed-tag')).not.toBeInTheDocument()
  })

  it('shows the weighted card with ratings only, no total or band, and no suggestion box, when scores are off', async () => {
    const report = {
      rows: [{ name: 'Strategy', weight: 100, key: true, rating: 4 }],
      points: 0, assessed_weight: 100, total_weight: 100, complete: true, score: null, band: null, bands: {},
      key_min_rating: 3, key_flags: [], unassessed: [], hidden: true,
    }
    api.get.mockResolvedValue({
      data: { ...BASE, ai_score: null, scores_hidden: true, score_report: report, ai_rationale: 'Strong on strategy.',
        record: { reference: 'EL-1', role: 'Sales', interview_date: null, duration_minutes: 10, interviewer: 'x',
          top_strengths: [], top_gaps: [], claims_to_verify: [], reference_check_questions: [], panel_decision: null } },
    })
    renderModal()

    expect(await screen.findByText('Strategy')).toBeInTheDocument()
    expect(screen.queryByTestId('weighted-total')).not.toBeInTheDocument()
    expect(screen.queryByTestId('weighted-band')).not.toBeInTheDocument()
    expect(screen.queryByText(/Suggested by the assessment/)).not.toBeInTheDocument()
  })

  const RECORD = {
    reference: 'EL-1', role: 'Sales', interview_date: null, duration_minutes: 10, interviewer: 'x',
    top_strengths: ['Owns the numbers'], top_gaps: [], claims_to_verify: [], reference_check_questions: [], panel_decision: null,
  }

  it('with the score number off shows the band and ratings, no total and no points, and the written assessment', async () => {
    const report = {
      rows: [{ name: 'Strategy', weight: 100, key: true, rating: 4 }],
      points: 0, assessed_weight: 100, total_weight: 100, complete: true, score: null, band: 'Shortlist', bands: {},
      key_min_rating: 3, key_flags: [], unassessed: [], number_hidden: true,
    }
    api.get.mockResolvedValue({
      data: { ...BASE, ai_score: null, score_number_hidden: true, score_report: report, ai_rationale: 'Strong on strategy.', record: RECORD },
    })
    renderModal()

    expect(await screen.findByTestId('weighted-band')).toHaveTextContent('Shortlist')
    expect(screen.queryByTestId('weighted-total')).not.toBeInTheDocument()
    expect(screen.queryByText('Points')).not.toBeInTheDocument()
    expect(screen.getByText('Strong on strategy.')).toBeInTheDocument()
  })

  it('with the gaps off has no gaps card in the record', async () => {
    api.get.mockResolvedValue({ data: { ...BASE, ai_score: 70, gaps_hidden: true, record: RECORD } })
    renderModal()

    expect(await screen.findByText('Top three demonstrated strengths')).toBeInTheDocument()
    expect(screen.queryByText('Top three gaps or risks')).not.toBeInTheDocument()
  })

  it('with the written assessment off shows no assessment text and not the empty-score message, but keeps the band', async () => {
    const report = {
      rows: [{ name: 'Strategy', weight: 100, key: true, rating: 4 }],
      points: 80, assessed_weight: 100, total_weight: 100, complete: true, score: 80, band: 'Shortlist', bands: { strong: 85, shortlist: 75, hold: 65 },
      key_min_rating: 3, key_flags: [], unassessed: [],
    }
    api.get.mockResolvedValue({
      data: { ...BASE, ai_score: 80, writeup_hidden: true, ai_rationale: null, score_report: report, record: RECORD },
    })
    renderModal()

    expect(await screen.findByTestId('weighted-band')).toHaveTextContent('Shortlist')
    expect(screen.queryByText(/No score is available/)).not.toBeInTheDocument()
    expect(screen.queryByText('A steady candidate.')).not.toBeInTheDocument()
  })

  it('with the written assessment off and no scoring profile shows no assessment card at all', async () => {
    api.get.mockResolvedValue({ data: { ...BASE, ai_score: 80, writeup_hidden: true, ai_rationale: null } })
    renderModal()

    await screen.findByText(/CV Assessment/i)
    expect(screen.queryByText('Interview Assessment')).not.toBeInTheDocument()
    expect(screen.queryByText(/No score is available/)).not.toBeInTheDocument()
  })

  it('shows the scorecard as it is printed, headed with the candidate, the role and the date, with a button to print it', async () => {
    const scorecard = {
      rows: [{ name: 'Strategy', weight: 100, key: true, rating: 4, points: 40, evidence: 'Mapped Lagos and ran a pilot.' }],
      total_points: 40, max_points: 50, total_score: 80, practical_rating: 4, strengths: ['Clear.'], decision: 'Proceed.', panel_decision: null, hidden: false,
    }
    api.get.mockResolvedValue({
      data: { ...BASE, ai_score: 80, ai_rationale: 'Fine.', scorecard, record: { role: 'National Sales Manager', top_strengths: [], top_gaps: [], claims_to_verify: [], reference_check_questions: [], reference: 'EL-1', interview_date: null, duration_minutes: 10, interviewer: 'x', panel_decision: null } },
    })
    renderModal()

    const section = await screen.findByRole('region', { name: 'Scorecard' })
    expect(within(section).getByRole('heading', { name: 'Interview Scorecard: National Sales Manager' })).toBeInTheDocument()
    expect(within(section).getByText(/Candidate Name:/).parentElement).toHaveTextContent('Candidate Name: Ada')
    expect(within(section).getByText('Mapped Lagos and ran a pilot.')).toBeInTheDocument()
    expect(within(section).getByRole('button', { name: /Download PDF/ })).toBeInTheDocument()
  })

  it('shows no scorecard for an interview scored without competencies', async () => {
    api.get.mockResolvedValue({ data: { ...BASE, ai_score: 62, ai_rationale: 'Fine.', scorecard: null } })
    renderModal()

    await screen.findByText('Fine.')
    expect(screen.queryByRole('region', { name: 'Scorecard' })).not.toBeInTheDocument()
  })

  it('shows a small Reviewed tag beside the score when a person at Elevare set it, and no admin panel', async () => {
    api.get.mockResolvedValue({ data: { ...BASE, ai_score: 89, ai_rationale: 'Strong answers.', reviewed: true } })
    renderModal()

    expect(await screen.findByTestId('reviewed-tag')).toHaveTextContent('Reviewed')
    expect(screen.queryByRole('region', { name: 'Review score' })).not.toBeInTheDocument()
  })

  it('shows no tag and no admin panel for the system’s own score', async () => {
    api.get.mockResolvedValue({ data: { ...BASE, ai_score: 62, ai_rationale: 'Fine.' } })
    renderModal()

    await screen.findByText('Fine.')
    expect(screen.queryByTestId('reviewed-tag')).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Review score' })).not.toBeInTheDocument()
  })

  it('shows the review panel to an administrator only, which is whoever the server sends the history to', async () => {
    api.get.mockResolvedValue({
      data: {
        ...BASE,
        ai_score: 58,
        ai_rationale: 'Fine.',
        score_review: { original_score: 58, original_band: null, reviews: [] },
      },
    })
    renderModal()

    expect(await screen.findByRole('region', { name: 'Review score' })).toBeInTheDocument()
  })

  it('reloads the interview after an administrator saves a score, and shows it tagged', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        ...BASE,
        ai_score: 58,
        ai_rationale: 'Fine.',
        score_review: { original_score: 58, original_band: null, original_rationale: 'Fine.', reviews: [] },
      },
    })
    api.put.mockResolvedValue({ data: { score: 89, band: null, reviewed: true } })
    api.get.mockResolvedValueOnce({
      data: {
        ...BASE,
        ai_score: 89,
        ai_rationale: 'Fine.',
        reviewed: true,
        score_review: { original_score: 58, original_band: null, original_rationale: 'Fine.', reviews: [] },
      },
    })
    renderModal()

    fireEvent.change(await screen.findByLabelText(/^Total \(0 to 100\)/), { target: { value: '89' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save score' }))

    expect(await screen.findByTestId('reviewed-tag')).toBeInTheDocument()
    expect(api.put).toHaveBeenCalledWith(
      '/api/v1/interviews/profile-1/score-review',
      { score: 89, ratings: null, rationale: null, reason: null },
      { params: { job_id: 'job-1' } }
    )
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

    fireEvent.click(await screen.findByRole('button', { name: /generate score/i }))

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

    fireEvent.click(await screen.findByRole('button', { name: /generate score/i }))

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

    fireEvent.click(await screen.findByRole('button', { name: /generate score/i }))
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

  it('asks before having the candidate retake it, and does nothing when the employer declines', async () => {
    api.get.mockResolvedValue({ data: ENDED })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { onReinstated } = renderEnded()

    fireEvent.click(await screen.findByRole('button', { name: 'Have them retake it' }))

    expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/deletes this attempt.s answers and recording/))
    expect(api.post).not.toHaveBeenCalled()
    expect(onReinstated).not.toHaveBeenCalled()
    confirm.mockRestore()
  })

  it('starts it over once confirmed, says the candidate takes it from the start, and tells the list', async () => {
    api.get.mockResolvedValue({ data: ENDED })
    api.post.mockResolvedValue({
      data: { outcome: 'started_over', status: 'PENDING', interview_url: 'https://x/i/t', email_sent: true },
    })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { onReinstated } = renderEnded()

    fireEvent.click(await screen.findByRole('button', { name: 'Have them retake it' }))

    expect(await screen.findByText('The interview was started over')).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledWith('/api/v1/interviews/profile-1/recover', null, {
      params: { job_id: 'job-1', start_over: true },
    })
    expect(screen.getByText(/from the start, with the full time/)).toBeInTheDocument()
    expect(onReinstated).toHaveBeenCalledTimes(1)
    confirm.mockRestore()
  })

  it('tells the owner to send the link themselves when a retake has no email on file', async () => {
    api.get.mockResolvedValue({ data: ENDED })
    api.post.mockResolvedValue({
      data: { outcome: 'started_over', status: 'PENDING', interview_url: 'https://x/i/t', email_sent: false },
    })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderEnded()

    fireEvent.click(await screen.findByRole('button', { name: 'Have them retake it' }))

    expect(await screen.findByText(/no email address on file/)).toBeInTheDocument()
    confirm.mockRestore()
  })

  it('shows the server’s words when a retake is refused, and the network message when there is no answer', async () => {
    api.get.mockResolvedValue({ data: ENDED })
    api.post.mockRejectedValueOnce({ response: { data: { message: 'Not enough credits' } } })
    api.post.mockRejectedValueOnce(new Error('network'))
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderEnded()

    fireEvent.click(await screen.findByRole('button', { name: 'Have them retake it' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Not enough credits')
    fireEvent.click(screen.getByRole('button', { name: 'Have them retake it' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('We could not reach the server'))
    confirm.mockRestore()
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

  it('shows the practical case apart from the score, when the interview had one', async () => {
    const practical = {
      question_number: 9, complete: true, score: 3.6, assessed_weight: 100, total_weight: 100, unassessed: [], summary: 'A workable plan.',
      rows: [
        { key: 'prioritisation', name: 'Prioritisation', weight: 30, rating: 4, rationale: 'Clear order.' },
        { key: 'realism', name: 'Realism', weight: 25, rating: 3, rationale: '' },
        { key: 'measurement', name: 'Measurement', weight: 20, rating: 3, rationale: '' },
        { key: 'risk', name: 'Risk and contingency', weight: 15, rating: 4, rationale: '' },
        { key: 'clarity', name: 'Clarity of communication', weight: 10, rating: 3, rationale: '' },
      ],
    }
    api.get.mockResolvedValue({ data: { ...BASE, ai_score: 72, ai_rationale: 'A steady candidate.', practical_case: practical } })
    renderEnded()

    expect(await screen.findByTestId('practical-score')).toHaveTextContent('3.6 / 5')
    expect(screen.getByText(/It is not part of the weighted score/)).toBeInTheDocument()
    expect(screen.getByText('Clear order.')).toBeInTheDocument()
  })

  describe('the assessment record and the panel decision', () => {
    const RECORD = {
      reference: 'EL-1A2B3C4D', role: 'Sales Manager', interview_date: '2026-10-20T09:17:40Z', duration_minutes: 18,
      interviewer: 'Elevare structured interview', top_strengths: ['Clear route to market'], top_gaps: ['Light on supply chain'],
      claims_to_verify: [], reference_check_questions: ['Who led the roll-out?'], panel_decision: null,
    }

    it('shows the record under the assessments', async () => {
      api.get.mockResolvedValue({ data: { ...BASE, ai_score: 72, ai_rationale: 'Fine.', record: RECORD } })
      renderEnded()

      expect(await screen.findByTestId('record-reference')).toHaveTextContent('EL-1A2B3C4D')
      expect(screen.getByText('Clear route to market')).toBeInTheDocument()
      expect(screen.getByText('Who led the roll-out?')).toBeInTheDocument()
    })

    it('records the panel decision for this candidate and job, and shows it at once with its sign-off', async () => {
      api.get.mockResolvedValue({ data: { ...BASE, ai_score: 72, ai_rationale: 'Fine.', record: RECORD } })
      api.put.mockResolvedValue({
        data: { decision: 'SHORTLIST', label: 'Shortlist', rationale: 'Good route to market.', decided_by_name: 'Ada Obi', decided_at: '2026-10-21T10:00:00Z' },
      })
      renderEnded()
      await screen.findByTestId('record-reference')

      fireEvent.change(screen.getByLabelText('Decision'), { target: { value: 'SHORTLIST' } })
      fireEvent.change(screen.getByLabelText('Reason for the decision'), { target: { value: 'Good route to market.' } })
      fireEvent.click(screen.getByRole('button', { name: 'Record decision' }))

      expect(await screen.findByTestId('latest-decision')).toHaveTextContent('Signed off by Ada Obi')
      expect(api.put).toHaveBeenCalledWith(
        expect.stringMatching(/^\/api\/v1\/interviews\/.+\/panel-decision$/),
        { decision: 'SHORTLIST', rationale: 'Good route to market.' },
        { params: { job_id: expect.any(String) } }
      )
    })

    it('suggests the band of a complete score, and the panel accepts it in one click', async () => {
      const report = {
        rows: [{ name: 'Strategy', weight: 100, key: false, rating: 4 }],
        points: 80, assessed_weight: 100, total_weight: 100, complete: true, score: 80, band: 'Shortlist',
        bands: { strong: 85, shortlist: 75, hold: 65 }, key_min_rating: 3, key_flags: [], unassessed: [],
      }
      api.get.mockResolvedValue({ data: { ...BASE, ai_score: 80, ai_rationale: 'Fine.', record: RECORD, score_report: report } })
      api.put.mockResolvedValue({
        data: { decision: 'SHORTLIST', label: 'Shortlist', rationale: 'x', decided_by_name: 'Ada Obi', decided_at: '2026-10-21T10:00:00Z' },
      })
      renderEnded()

      expect(await screen.findByTestId('suggested-decision')).toHaveTextContent('Shortlist, score 80 of 100')
      fireEvent.click(screen.getByRole('button', { name: 'Accept this suggestion' }))

      expect(await screen.findByTestId('latest-decision')).toHaveTextContent('Matches the suggestion.')
      expect(api.put).toHaveBeenCalledWith(
        expect.stringMatching(/panel-decision$/),
        { decision: 'SHORTLIST', rationale: 'Agreed with the suggested band: Shortlist (score 80 of 100).' },
        { params: { job_id: expect.any(String) } }
      )
    })

    it('does not offer to decide on an interview that is still in progress, and says why', async () => {
      api.get.mockResolvedValue({ data: { ...BASE, status: 'IN_PROGRESS', record: RECORD } })
      renderEnded()

      await screen.findByTestId('record-reference')
      expect(screen.getByText('The interview has not finished yet, so there is nothing to decide on.')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Record decision' })).toBeDisabled()
    })

    it('shows no record for an interview whose detail has none, as an older server sends', async () => {
      api.get.mockResolvedValue({ data: { ...BASE, ai_score: 72, ai_rationale: 'Fine.' } })
      renderEnded()

      await screen.findByText(/Transcript/)
      expect(screen.queryByTestId('assessment-record')).not.toBeInTheDocument()
    })
  })

  it('shows no practical case card for an interview without one', async () => {
    api.get.mockResolvedValue({ data: { ...BASE, ai_score: 72, ai_rationale: 'A steady candidate.' } })
    renderEnded()

    await screen.findByText(/Transcript/)
    expect(screen.queryByTestId('practical-case')).not.toBeInTheDocument()
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
    expect(screen.queryByText(/No score is available/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Generate score' })).not.toBeInTheDocument()
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
    expect(screen.queryByRole('button', { name: /generate score/i })).not.toBeInTheDocument()
  })
})

describe('InterviewDetailModal, an admin scoring the interview again', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    api.get.mockReset()
    api.post.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  const REPORT = {
    rows: [{ name: 'Strategy', weight: 100, key: true, rating: 4 }],
    points: 80, assessed_weight: 100, total_weight: 100, complete: true, score: 80, band: 'Shortlist',
    bands: { strong: 85, shortlist: 75, hold: 65 }, key_min_rating: 3, key_flags: [], unassessed: [],
  }
  const RECORD = {
    reference: 'EL-1', role: 'Sales', interview_date: null, duration_minutes: 10, interviewer: 'x',
    top_strengths: ['Owns the numbers'], top_gaps: [], claims_to_verify: [], reference_check_questions: [], panel_decision: null,
  }
  const REVIEW = { original_score: 80, original_band: 'Shortlist', original_ratings: { Strategy: 4 }, reviews: [] }
  const SCORED = {
    ...BASE, ai_score: 80, ai_rationale: 'Strong on strategy.', score_report: REPORT, record: RECORD, score_review: REVIEW,
    video_url: 'https://signed.example/v', rescore: null,
  }
  const pending = { status: 'PENDING', requested_at: '2026-10-29T10:00:00Z', error: null, stale: false }

  it('hides the earlier result and says it is being scored again, keeping the recording and transcript', async () => {
    api.get.mockResolvedValue({ data: { ...SCORED, rescore: pending } })
    renderModal()

    expect(await screen.findByTestId('rescore-pending')).toHaveTextContent('Scoring this interview again')
    expect(screen.queryByTestId('weighted-band')).not.toBeInTheDocument()
    expect(screen.queryByTestId('weighted-total')).not.toBeInTheDocument()
    expect(screen.queryByText('Strong on strategy.')).not.toBeInTheDocument()
    expect(screen.queryByText('Top three demonstrated strengths')).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Review score' })).not.toBeInTheDocument()
    expect(screen.queryByText(/No score is available/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /generate score/i })).not.toBeInTheDocument()
    expect(screen.getByText(/Hello/)).toBeInTheDocument()
  })

  it('checks again by itself and fills in the new result when it arrives', async () => {
    api.get.mockResolvedValueOnce({ data: { ...SCORED, rescore: pending } })
    api.get.mockResolvedValue({ data: { ...SCORED, ai_score: 71, ai_rationale: 'A fair showing.', rescore: null, score_report: { ...REPORT, score: 71, band: 'Hold for evidence' } } })
    renderModal()
    await screen.findByTestId('rescore-pending')

    await act(async () => {
      await vi.advanceTimersByTimeAsync(RESCORE_POLL_INTERVAL_MS)
    })

    expect(await screen.findByTestId('weighted-band')).toHaveTextContent('Hold for evidence')
    expect(screen.queryByTestId('rescore-pending')).not.toBeInTheDocument()
    expect(screen.getAllByText('A fair showing.').length).toBeGreaterThan(0)
  })

  it('keeps waiting when a check fails, and stops checking once it is no longer pending', async () => {
    api.get.mockResolvedValueOnce({ data: { ...SCORED, rescore: pending } })
    api.get.mockRejectedValueOnce(new Error('network'))
    api.get.mockResolvedValue({ data: { ...SCORED, rescore: null } })
    renderModal()
    await screen.findByTestId('rescore-pending')

    await act(async () => {
      await vi.advanceTimersByTimeAsync(RESCORE_POLL_INTERVAL_MS)
    })
    expect(screen.getByTestId('rescore-pending')).toBeInTheDocument()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(RESCORE_POLL_INTERVAL_MS)
    })
    await screen.findByTestId('weighted-band')
    const calls = api.get.mock.calls.length
    await act(async () => {
      await vi.advanceTimersByTimeAsync(RESCORE_POLL_INTERVAL_MS * 3)
    })

    expect(api.get.mock.calls.length).toBe(calls)
  })

  it('says it did not finish, with the reason, and shows the earlier result and the way to ask again', async () => {
    api.get.mockResolvedValue({
      data: { ...SCORED, rescore: { status: 'FAILED', requested_at: '2026-10-29T10:00:00Z', error: 'The scoring did not return a usable result.', stale: false } },
    })
    renderModal()

    const notice = await screen.findByTestId('rescore-failed')
    expect(notice).toHaveTextContent('did not finish')
    expect(notice).toHaveTextContent('The scoring did not return a usable result.')
    expect(notice).toHaveTextContent('The earlier result is unchanged')
    expect(screen.getByTestId('weighted-band')).toHaveTextContent('Shortlist')
    expect(screen.getByRole('button', { name: 'Score this interview again' })).toBeInTheDocument()
  })

  it('treats a request that has been pending too long as lost, not as running', async () => {
    api.get.mockResolvedValue({ data: { ...SCORED, rescore: { ...pending, stale: true } } })
    renderModal()

    const notice = await screen.findByTestId('rescore-failed')
    expect(notice).toHaveTextContent('no answer after ten minutes')
    expect(screen.queryByTestId('rescore-pending')).not.toBeInTheDocument()
    expect(screen.getByTestId('weighted-band')).toBeInTheDocument()
  })

  it('shows nothing extra when nothing is open', async () => {
    api.get.mockResolvedValue({ data: SCORED })
    renderModal()

    await screen.findByTestId('weighted-band')
    expect(screen.queryByTestId('rescore-pending')).not.toBeInTheDocument()
    expect(screen.queryByTestId('rescore-failed')).not.toBeInTheDocument()
  })
})
