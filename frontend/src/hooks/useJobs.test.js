import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useJobs } from './useJobs'

// Mock the api module
vi.mock('@/lib/api', () => ({
  default: {
    get: vi.fn(),
  },
}))

import api from '@/lib/api'

const makeResponse = (items, next_cursor = null) => ({
  data: { items, next_cursor, count: items.length },
})

const makeJob = (id) => ({ id: String(id), title: `Job ${id}` })

describe('useJobs', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('fetches jobs on mount and exposes them', async () => {
    const jobs = [makeJob(1), makeJob(2)]
    api.get.mockResolvedValueOnce(makeResponse(jobs))

    const { result } = renderHook(() => useJobs())

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.jobs).toEqual(jobs)
    expect(result.current.error).toBeNull()
    expect(result.current.hasMore).toBe(false)
  })

  it('sets hasMore=true when next_cursor is a non-empty string', async () => {
    api.get.mockResolvedValueOnce(makeResponse([makeJob(1)], 'cursor-abc'))

    const { result } = renderHook(() => useJobs())

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.hasMore).toBe(true)
  })

  it('sets hasMore=false when next_cursor is null', async () => {
    api.get.mockResolvedValueOnce(makeResponse([makeJob(1)], null))

    const { result } = renderHook(() => useJobs())

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.hasMore).toBe(false)
  })

  it('loadMore appends jobs to the existing list', async () => {
    const page1 = [makeJob(1), makeJob(2)]
    const page2 = [makeJob(3), makeJob(4)]
    api.get
      .mockResolvedValueOnce(makeResponse(page1, 'cursor-1'))
      .mockResolvedValueOnce(makeResponse(page2, null))

    const { result } = renderHook(() => useJobs())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.jobs).toEqual(page1)

    await act(async () => {
      result.current.loadMore()
    })

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.jobs).toEqual([...page1, ...page2])
    expect(result.current.hasMore).toBe(false)
  })

  it('resets jobs when params change', async () => {
    const page1 = [makeJob(1)]
    const page2 = [makeJob(99)]
    api.get
      .mockResolvedValueOnce(makeResponse(page1, null))
      .mockResolvedValueOnce(makeResponse(page2, null))

    const { result, rerender } = renderHook(
      ({ params }) => useJobs({ params }),
      { initialProps: { params: { contract_type: 'FULL_TIME' } } }
    )

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.jobs).toEqual(page1)

    rerender({ params: { contract_type: 'PART_TIME' } })

    await waitFor(() => expect(result.current.loading).toBe(false))

    // After filter change, only the new page's items should be present
    expect(result.current.jobs).toEqual(page2)
    expect(result.current.jobs).not.toContainEqual(makeJob(1))
  })

  it('preserves existing jobs on error during loadMore', async () => {
    const page1 = [makeJob(1), makeJob(2)]
    api.get
      .mockResolvedValueOnce(makeResponse(page1, 'cursor-1'))
      .mockRejectedValueOnce(new Error('Network error'))

    const { result } = renderHook(() => useJobs())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.jobs).toEqual(page1)

    await act(async () => {
      result.current.loadMore()
    })

    await waitFor(() => expect(result.current.loading).toBe(false))

    // Jobs should be preserved, error should be set
    expect(result.current.jobs).toEqual(page1)
    expect(result.current.error).not.toBeNull()
  })
})
