import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { put: vi.fn(), delete: vi.fn() } }))

import api from '@/lib/api'
import ScoreReviewPanel from './ScoreReviewPanel'

const BANDS = { strong: 85, shortlist: 75, hold: 65 }

// A job with no competencies: only the total can be set.
const PLAIN = {
  ai_score: 58,
  reviewed: false,
  score_report: { bands: BANDS, score: 58, band: 'Do not shortlist', rows: [] },
  score_review: { original_score: 58, original_band: 'Do not shortlist', original_ratings: {}, reviews: [] },
}

// Strategy (60%, key) and P&L (40%), both rated 3 by the system: a total of 60.
const ROWS = [
  { name: 'Strategy', weight: 60, key: true, rating: 3 },
  { name: 'P&L', weight: 40, key: false, rating: 3 },
]
const WITH_ROWS = {
  ai_score: 60,
  reviewed: false,
  score_report: { bands: BANDS, score: 60, band: 'Do not shortlist', rows: ROWS },
  score_review: { original_score: 60, original_band: 'Do not shortlist', original_ratings: { Strategy: 3, 'P&L': 3 }, reviews: [] },
}

function setup(detail = PLAIN) {
  const onChanged = vi.fn(async () => {})
  render(<ScoreReviewPanel jobId="job-1" talentPoolProfileId="p-1" detail={detail} onChanged={onChanged} />)
  return { onChanged }
}

const totalInput = () => screen.getByLabelText(/^Total \(0 to 100\)/)
const save = () => screen.getByRole('button', { name: 'Save score' })
const rating = (name) => screen.getByLabelText(`Rating for ${name}`)

describe('ScoreReviewPanel, the total', () => {
  beforeEach(() => vi.clearAllMocks())

  it('says it is for Elevare administrators, and shows the system’s own score and band', () => {
    setup()

    expect(screen.getByText(/visible to Elevare administrators only/)).toBeInTheDocument()
    expect(screen.getByTestId('system-score')).toHaveTextContent('System score: 58, Do not shortlist')
    expect(totalInput()).toHaveValue(58)
    expect(save()).toBeDisabled()
  })

  it('previews the band the new total gives by the job’s own cut-offs', () => {
    setup()

    for (const [score, band] of [['89', 'Strong shortlist'], ['80', 'Shortlist'], ['70', 'Hold for evidence'], ['10', 'Do not shortlist']]) {
      fireEvent.change(totalInput(), { target: { value: score } })
      expect(screen.getByTestId('band-preview')).toHaveTextContent(band)
    }
  })

  it('saves the total with an optional reason, then asks the window to reload', async () => {
    api.put.mockResolvedValueOnce({ data: { score: 89, band: 'Strong shortlist', reviewed: true } })
    const { onChanged } = setup()

    fireEvent.change(totalInput(), { target: { value: '89' } })
    fireEvent.change(screen.getByLabelText('Reason (optional)'), { target: { value: '  Panel read it differently ' } })
    fireEvent.click(save())

    await waitFor(() => expect(onChanged).toHaveBeenCalled())
    expect(api.put).toHaveBeenCalledWith(
      '/api/v1/interviews/p-1/score-review',
      { score: 89, ratings: null, rationale: null, reason: 'Panel read it differently' },
      { params: { job_id: 'job-1' } }
    )
  })

  it('needs no reason', async () => {
    api.put.mockResolvedValueOnce({ data: {} })
    setup()

    fireEvent.change(totalInput(), { target: { value: '70' } })
    fireEvent.click(save())

    await waitFor(() => expect(api.put).toHaveBeenCalled())
    expect(api.put.mock.calls[0][1]).toEqual({ score: 70, ratings: null, rationale: null, reason: null })
  })

  it('does not save an empty total, one outside 0 to 100, or the total it already has', () => {
    setup()

    for (const value of ['', '101', '-1', '58']) {
      fireEvent.change(totalInput(), { target: { value } })
      expect(save()).toBeDisabled()
    }
    fireEvent.change(totalInput(), { target: { value: '0' } })
    expect(save()).toBeEnabled()
  })

  it('offers to remove a review, and the request takes it away', async () => {
    api.delete.mockResolvedValueOnce({ data: {} })
    const { onChanged } = setup({ ...PLAIN, ai_score: 89, reviewed: true })

    fireEvent.click(screen.getByRole('button', { name: /Remove the review/ }))

    await waitFor(() => expect(onChanged).toHaveBeenCalled())
    expect(api.delete).toHaveBeenCalledWith('/api/v1/interviews/p-1/score-review', { params: { job_id: 'job-1' } })
  })

  it('offers no removal when nothing has been reviewed', () => {
    setup()

    expect(screen.queryByRole('button', { name: /Remove the review/ })).not.toBeInTheDocument()
  })

  it('lists the history with who, when, what changed and why', () => {
    setup({
      ...PLAIN,
      ai_score: 89,
      reviewed: true,
      score_review: {
        ...PLAIN.score_review,
        reviews: [
          { score: 89, ratings: { Strategy: 5 }, reason: 'Panel read it differently', reviewed_by_name: 'Ada Admin', reviewed_at: '2026-10-29T10:00:00Z' },
          { score: null, ratings: {}, reason: null, reviewed_by_name: 'Bola Admin', reviewed_at: '2026-10-28T10:00:00Z' },
        ],
      },
    })

    const history = screen.getByTestId('review-history')
    expect(history).toHaveTextContent('Reviewed, total set to 89, ratings Strategy 5 by Ada Admin')
    expect(history).toHaveTextContent('Panel read it differently')
    expect(history).toHaveTextContent('Review removed by Bola Admin')
  })

  it('shows the server’s words when it refuses, and the network message when there is no answer', async () => {
    api.put.mockRejectedValueOnce({ response: { data: { message: 'Only a scored interview can have its score reviewed.' } } })
    api.put.mockRejectedValueOnce(new Error('network'))
    setup()

    fireEvent.change(totalInput(), { target: { value: '89' } })
    fireEvent.click(save())
    expect(await screen.findByRole('alert')).toHaveTextContent('Only a scored interview')

    fireEvent.click(save())
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('We could not reach the server'))
  })
})

describe('ScoreReviewPanel, the competency ratings', () => {
  beforeEach(() => vi.clearAllMocks())

  it('lists every competency with its weight, the system’s rating and a rating to change', () => {
    setup(WITH_ROWS)

    const table = within(screen.getByRole('table', { name: 'Competency ratings' }))
    const strategy = table.getByText('Strategy').closest('tr')
    expect(strategy).toHaveTextContent('60%')
    expect(rating('Strategy')).toHaveValue('3')
    expect(rating('P&L')).toHaveValue('3')
    expect(totalInput()).toHaveValue(60)
  })

  it('works the total out from the ratings as they are changed, with the band that follows', () => {
    setup(WITH_ROWS)

    fireEvent.change(rating('Strategy'), { target: { value: '5' } })

    expect(totalInput()).toHaveValue(84) // 60 * 5/5 + 40 * 3/5
    expect(screen.getByTestId('band-preview')).toHaveTextContent('Shortlist')
    fireEvent.change(rating('P&L'), { target: { value: '5' } })
    expect(totalInput()).toHaveValue(100)
    expect(screen.getByTestId('band-preview')).toHaveTextContent('Strong shortlist')
  })

  it('sends only the ratings that differ from the system’s, and no total, when the total was worked out', async () => {
    api.put.mockResolvedValueOnce({ data: {} })
    setup(WITH_ROWS)

    fireEvent.change(rating('Strategy'), { target: { value: '5' } })
    fireEvent.click(save())

    await waitFor(() => expect(api.put).toHaveBeenCalled())
    expect(api.put.mock.calls[0][1]).toEqual({ score: null, ratings: { Strategy: 5 }, rationale: null, reason: null })
  })

  it('sends the typed total as well, which wins over the ratings, once the total is typed', async () => {
    api.put.mockResolvedValueOnce({ data: {} })
    setup(WITH_ROWS)

    fireEvent.change(rating('Strategy'), { target: { value: '4' } })
    fireEvent.change(totalInput(), { target: { value: '95' } })
    fireEvent.change(rating('P&L'), { target: { value: '4' } })
    expect(totalInput()).toHaveValue(95) // a typed total stays while the ratings change
    fireEvent.click(save())

    await waitFor(() => expect(api.put).toHaveBeenCalled())
    expect(api.put.mock.calls[0][1]).toEqual({ score: 95, ratings: { Strategy: 4, 'P&L': 4 }, rationale: null, reason: null })
  })

  it('goes back to working the total out from the ratings on request', () => {
    setup(WITH_ROWS)

    fireEvent.change(rating('Strategy'), { target: { value: '5' } })
    fireEvent.change(totalInput(), { target: { value: '95' } })
    fireEvent.click(screen.getByRole('button', { name: 'Work the total out from the ratings' }))

    expect(totalInput()).toHaveValue(84)
  })

  it('does not offer to save until something has changed', () => {
    setup(WITH_ROWS)

    expect(save()).toBeDisabled()
    fireEvent.change(rating('Strategy'), { target: { value: '4' } })
    expect(save()).toBeEnabled()
    fireEvent.change(rating('Strategy'), { target: { value: '3' } })
    expect(save()).toBeDisabled()
  })

  it('lets a competency the system could not assess be rated, which completes the total', () => {
    const detail = {
      ...WITH_ROWS,
      ai_score: null,
      score_report: { ...WITH_ROWS.score_report, rows: [{ ...ROWS[0] }, { ...ROWS[1], rating: null }] },
      score_review: { ...WITH_ROWS.score_review, original_ratings: { Strategy: 3, 'P&L': null } },
    }
    setup(detail)

    expect(rating('P&L')).toHaveValue('')
    expect(totalInput()).toHaveValue(null)
    fireEvent.change(rating('P&L'), { target: { value: '4' } })

    expect(totalInput()).toHaveValue(68) // 60 * 3/5 + 40 * 4/5
  })

  it('opens on a reviewed interview with the reviewer’s ratings, and keeps a typed total typed', () => {
    setup({
      ...WITH_ROWS,
      ai_score: 95,
      reviewed: true,
      score_report: { ...WITH_ROWS.score_report, rows: [{ ...ROWS[0], rating: 5 }, ROWS[1]] },
    })

    expect(rating('Strategy')).toHaveValue('5')
    expect(totalInput()).toHaveValue(95)
    expect(screen.getByRole('button', { name: 'Work the total out from the ratings' })).toBeInTheDocument()
  })
})

describe('ScoreReviewPanel, the written assessment', () => {
  beforeEach(() => vi.clearAllMocks())

  const SYSTEM_TEXT = 'A steady candidate.\n\nWeighted score: 60 of 100. Suggested band (provisional): Do not shortlist.'
  const WITH_TEXT = {
    ...WITH_ROWS,
    ai_rationale: SYSTEM_TEXT,
    score_review: { ...WITH_ROWS.score_review, original_rationale: SYSTEM_TEXT },
  }
  const textBox = () => screen.getByLabelText(/^Written assessment/)

  it('shows the text everyone reads, ready to edit, and says the system’s text is kept', () => {
    setup(WITH_TEXT)

    expect(textBox()).toHaveValue(SYSTEM_TEXT)
    expect(screen.getByText(/The system.s own text is kept and can be put back/)).toBeInTheDocument()
    expect(save()).toBeDisabled()
    expect(screen.queryByRole('button', { name: /Use the system.s text/ })).not.toBeInTheDocument()
  })

  it('saves an edited text on its own, with nothing else changed', async () => {
    api.put.mockResolvedValueOnce({ data: {} })
    const { onChanged } = setup(WITH_TEXT)

    fireEvent.change(textBox(), { target: { value: '  A confident operator with a clear route to market.  ' } })
    fireEvent.click(save())

    await waitFor(() => expect(onChanged).toHaveBeenCalled())
    expect(api.put).toHaveBeenCalledWith(
      '/api/v1/interviews/p-1/score-review',
      { score: null, ratings: null, rationale: 'A confident operator with a clear route to market.', reason: null },
      { params: { job_id: 'job-1' } }
    )
  })

  it('sends the text together with changed ratings', async () => {
    api.put.mockResolvedValueOnce({ data: {} })
    setup(WITH_TEXT)

    fireEvent.change(rating('Strategy'), { target: { value: '5' } })
    fireEvent.change(textBox(), { target: { value: 'Rewritten.' } })
    fireEvent.click(save())

    await waitFor(() => expect(api.put).toHaveBeenCalled())
    expect(api.put.mock.calls[0][1]).toEqual({ score: null, ratings: { Strategy: 5 }, rationale: 'Rewritten.', reason: null })
  })

  it('offers to put the system’s text back, and sends no text when the box equals it', async () => {
    api.put.mockResolvedValueOnce({ data: {} })
    setup(WITH_TEXT)

    fireEvent.change(textBox(), { target: { value: 'Something else.' } })
    fireEvent.click(screen.getByRole('button', { name: /Use the system.s text/ }))
    expect(textBox()).toHaveValue(SYSTEM_TEXT)
    expect(save()).toBeDisabled() // back to the system's text and nothing else changed

    fireEvent.change(rating('Strategy'), { target: { value: '4' } })
    fireEvent.click(save())
    await waitFor(() => expect(api.put).toHaveBeenCalled())
    expect(api.put.mock.calls[0][1].rationale).toBeNull()
  })

  it('keeps an earlier written assessment when something else is changed', async () => {
    api.put.mockResolvedValueOnce({ data: {} })
    const written = 'The admin’s earlier text.'
    setup({ ...WITH_TEXT, ai_rationale: written, reviewed: true })

    expect(textBox()).toHaveValue(written)
    fireEvent.change(rating('Strategy'), { target: { value: '5' } })
    fireEvent.click(save())

    await waitFor(() => expect(api.put).toHaveBeenCalled())
    expect(api.put.mock.calls[0][1].rationale).toBe(written)
  })

  it('does not save an empty text as a new assessment', () => {
    setup(WITH_TEXT)

    fireEvent.change(textBox(), { target: { value: '   ' } })

    expect(save()).toBeDisabled()
  })

  it('does not send a total just because the text was edited on a job without competencies', async () => {
    api.put.mockResolvedValueOnce({ data: {} })
    setup({ ...PLAIN, ai_rationale: 'System text.', score_review: { ...PLAIN.score_review, original_rationale: 'System text.' } })

    fireEvent.change(textBox(), { target: { value: 'Admin text.' } })
    fireEvent.click(save())

    await waitFor(() => expect(api.put).toHaveBeenCalled())
    expect(api.put.mock.calls[0][1]).toEqual({ score: null, ratings: null, rationale: 'Admin text.', reason: null })
  })

  it('lists an edited written assessment in the history', () => {
    setup({
      ...WITH_TEXT,
      reviewed: true,
      score_review: {
        ...WITH_TEXT.score_review,
        reviews: [{ score: null, ratings: {}, rationale_changed: true, reason: null, reviewed_by_name: 'Ada Admin', reviewed_at: '2026-10-29T10:00:00Z' }],
      },
    })

    expect(screen.getByTestId('review-history')).toHaveTextContent('Reviewed, written assessment edited by Ada Admin')
  })
})
