import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

import api from '@/lib/api'
import { useRescore } from './useRescore'

const STATUS = { applications: 2, pipeline: 1, total: 3 }
const DONE = { scoring: 3, reparsing: 0, in_progress: 0, no_stored_file: 0, remaining: 0 }

describe('useRescore', () => {
  beforeEach(() => vi.clearAllMocks())

  it('loads how many candidates could be rescored', async () => {
    api.get.mockResolvedValueOnce({ data: STATUS })
    const { result } = renderHook(() => useRescore('job-1'))

    await waitFor(() => expect(result.current.status).toEqual(STATUS))
    expect(api.get).toHaveBeenCalledWith('/api/v1/rescore/jobs/job-1')
  })

  it('stays quiet when the count cannot be loaded', async () => {
    api.get.mockRejectedValueOnce(new Error('network'))
    const { result } = renderHook(() => useRescore('job-1'))

    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(result.current.status).toBeNull()
  })

  it('rescores, keeps the answer, and reloads the count', async () => {
    api.get.mockResolvedValueOnce({ data: STATUS }).mockResolvedValueOnce({ data: { applications: 0, pipeline: 0, total: 0 } })
    api.post.mockResolvedValueOnce({ data: DONE })
    const { result } = renderHook(() => useRescore('job-1'))
    await waitFor(() => expect(result.current.status).toEqual(STATUS))

    let outcome
    await act(async () => { outcome = await result.current.rescore({}) })

    expect(api.post).toHaveBeenCalledWith('/api/v1/rescore/jobs/job-1', {})
    expect(outcome).toEqual({ ok: true, data: DONE })
    expect(result.current.result).toEqual(DONE)
    expect(result.current.status.total).toBe(0)
    expect(result.current.working).toBe(false)
  })

  it('can rescore one candidate by name, and leaves the "rescore all" message alone', async () => {
    api.get.mockResolvedValue({ data: STATUS })
    api.post.mockResolvedValueOnce({ data: DONE })
    const { result } = renderHook(() => useRescore('job-1'))

    let outcome
    await act(async () => { outcome = await result.current.rescore({ application_id: 'a1' }) })

    expect(api.post).toHaveBeenCalledWith('/api/v1/rescore/jobs/job-1', { application_id: 'a1' })
    expect(outcome).toEqual({ ok: true, data: DONE })
    expect(result.current.result).toBeNull()
  })

  it('passes on the server\'s own message, so a plan limit reads as one', async () => {
    api.get.mockResolvedValue({ data: STATUS })
    api.post.mockRejectedValueOnce({
      response: { data: { code: 'PLAN_UPGRADE_REQUIRED', message: 'This feature requires a Professional plan or above' } },
    })
    const { result } = renderHook(() => useRescore('job-1'))

    let outcome
    await act(async () => { outcome = await result.current.rescore({}) })

    expect(outcome).toEqual({ ok: false, message: 'This feature requires a Professional plan or above' })
    expect(result.current.result).toBeNull()
    expect(result.current.working).toBe(false)
  })

  it('has a generic message when the server gave none', async () => {
    api.get.mockResolvedValue({ data: STATUS })
    api.post.mockRejectedValueOnce(new Error('network'))
    const { result } = renderHook(() => useRescore('job-1'))

    let outcome
    await act(async () => { outcome = await result.current.rescore({}) })

    expect(outcome.ok).toBe(false)
    expect(outcome.message).toMatch(/Could not start the rescore/)
  })

  it('can hide the answer', async () => {
    api.get.mockResolvedValue({ data: STATUS })
    api.post.mockResolvedValueOnce({ data: DONE })
    const { result } = renderHook(() => useRescore('job-1'))
    await act(async () => { await result.current.rescore({}) })

    act(() => result.current.dismissResult())

    expect(result.current.result).toBeNull()
  })
})
