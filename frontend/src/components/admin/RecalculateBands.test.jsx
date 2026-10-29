import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { post: vi.fn() } }))

import api from '@/lib/api'
import RecalculateBands from './RecalculateBands'

const URL = '/api/v1/interviews/jobs/job-1/recalculate-bands'
const change = (from_band, to_band) => ({ talent_pool_profile_id: 'p', from_score: 60, to_score: 60, from_band, to_band })
const ask = () => fireEvent.click(screen.getByRole('button', { name: 'Recalculate bands' }))
const confirm = () => fireEvent.click(screen.getByRole('button', { name: 'Yes, recalculate' }))

describe('RecalculateBands', () => {
  beforeEach(() => vi.clearAllMocks())

  it('asks first, saying nothing is sent to the model and no rating changes, and does nothing if cancelled', () => {
    render(<RecalculateBands jobId="job-1" />)

    ask()

    expect(screen.getByText(/No ratings change and nothing is sent to the model/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(api.post).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Recalculate bands' })).toBeInTheDocument()
  })

  it('asks the server once confirmed and says what changed, grouped by move, and refreshes the list', async () => {
    const onDone = vi.fn()
    api.post.mockResolvedValueOnce({
      data: {
        checked: 6, changed: 4, unchanged: 2, incomplete: 0, skipped: 0,
        changes: [
          change('Hold for evidence', 'Shortlist'), change('Hold for evidence', 'Shortlist'),
          change('Do not shortlist', 'Hold for evidence'), change('Shortlist', 'Strong shortlist'),
        ],
      },
    })
    render(<RecalculateBands jobId="job-1" onDone={onDone} />)
    ask()

    confirm()

    expect(await screen.findByTestId('recalculate-result')).toHaveTextContent('Checked 6 interviews: 4 changed, 2 unchanged.')
    expect(api.post).toHaveBeenCalledWith(URL)
    expect(screen.getByText('Hold for evidence to Shortlist: 2')).toBeInTheDocument()
    expect(screen.getByText('Do not shortlist to Hold for evidence: 1')).toBeInTheDocument()
    expect(screen.getByText('Shortlist to Strong shortlist: 1')).toBeInTheDocument()
    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('says nothing needed to change, and does not refresh the list, when nothing moved', async () => {
    const onDone = vi.fn()
    api.post.mockResolvedValueOnce({ data: { checked: 3, changed: 0, unchanged: 3, incomplete: 0, skipped: 0, changes: [] } })
    render(<RecalculateBands jobId="job-1" onDone={onDone} />)
    ask()
    confirm()

    expect(await screen.findByTestId('recalculate-result')).toHaveTextContent('Checked 3 interviews: nothing needed to change.')
    expect(onDone).not.toHaveBeenCalled()
  })

  it('says there is nothing to do on a job with no scored interviews', async () => {
    api.post.mockResolvedValueOnce({ data: { checked: 0, changed: 0, unchanged: 0, incomplete: 0, skipped: 0, changes: [] } })
    render(<RecalculateBands jobId="job-1" />)
    ask()
    confirm()

    expect(await screen.findByTestId('recalculate-result')).toHaveTextContent('There are no scored interviews on this job.')
  })

  it('warns about interviews that now have no total because the profile has a competency they never covered, and about skipped ones', async () => {
    api.post.mockResolvedValueOnce({
      data: { checked: 3, changed: 2, unchanged: 0, incomplete: 2, skipped: 1, changes: [change('Shortlist', null), change('Hold for evidence', null)] },
    })
    render(<RecalculateBands jobId="job-1" />)
    ask()
    confirm()

    expect(await screen.findByText(/2 now have no total or band/)).toBeInTheDocument()
    expect(screen.getByText(/Score them again to fill it in/)).toBeInTheDocument()
    expect(screen.getByText(/1 skipped/)).toBeInTheDocument()
  })

  it('shows the server’s words when it is refused, such as a job with no scoring profile, and lets the admin go back', async () => {
    api.post.mockRejectedValueOnce({ response: { data: { code: 'NO_SCORING_PROFILE', message: 'This job has no scoring profile, so there is nothing to weigh the ratings by.' } } })
    render(<RecalculateBands jobId="job-1" />)
    ask()
    confirm()

    expect(await screen.findByRole('alert')).toHaveTextContent('This job has no scoring profile')
    expect(screen.getByRole('button', { name: 'Yes, recalculate' })).toBeEnabled()
  })

  it('says it could not reach the server when there is no answer', async () => {
    api.post.mockRejectedValueOnce(new Error('Network Error'))
    render(<RecalculateBands jobId="job-1" />)
    ask()
    confirm()

    expect(await screen.findByRole('alert')).toHaveTextContent('We could not reach the server')
  })
})
