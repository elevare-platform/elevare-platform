import { useState, useEffect, useCallback, useRef } from 'react'
import api from '@/lib/api'

/**
 * useJobs — cursor-paginated job fetching hook.
 *
 * Separates initial-fetch loading from load-more loading so the existing
 * job list is never replaced with skeletons when appending a new page.
 *
 * @param {Object} options
 * @param {string} [options.endpoint='/api/v1/jobs']
 * @param {Object} [options.params={}]
 * @returns {{
 *   jobs: Array,
 *   loading: boolean,       — true only during the initial/reset fetch
 *   loadingMore: boolean,   — true only while appending the next page
 *   error: string|null,     — initial fetch error
 *   loadMoreError: string|null, — load-more error (preserved after append fails)
 *   hasMore: boolean,
 *   loadMore: () => void,
 * }}
 */
export function useJobs({ endpoint = '/api/v1/jobs', params = {} } = {}) {
  const [jobs, setJobs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(null)
  const [loadMoreError, setLoadMoreError] = useState(null)
  const [hasMore, setHasMore] = useState(false)

  const cursorRef = useRef(null)
  const paramsKey = JSON.stringify({ endpoint, ...params })

  // ── Initial / reset fetch ────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false

    const fetchFirstPage = async () => {
      setLoading(true)
      setError(null)
      setLoadMoreError(null)
      setJobs([])
      setTotal(0)
      setHasMore(false)
      cursorRef.current = null

      const cleanParams = Object.fromEntries(
        Object.entries(params).filter(([, v]) => v != null && v !== '')
      )

      try {
        const { data } = await api.get(endpoint, { params: cleanParams })
        if (cancelled) return
        setJobs(data.items ?? [])
        setTotal(data.total ?? data.items?.length ?? 0)
        cursorRef.current = data.next_cursor ?? null
        setHasMore(typeof data.next_cursor === 'string' && data.next_cursor.length > 0)
      } catch (err) {
        if (cancelled) return
        setError(err?.response?.data?.detail ?? err.message ?? 'Failed to load jobs')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchFirstPage()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey])

  // ── Append next page ─────────────────────────────────────────────────────
  const loadMore = useCallback(async () => {
    if (!cursorRef.current || loadingMore) return

    setLoadingMore(true)
    setLoadMoreError(null)

    const cleanParams = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v != null && v !== '')
    )

    try {
      const { data } = await api.get(endpoint, {
        params: { ...cleanParams, cursor: cursorRef.current },
      })
      setJobs((prev) => [...prev, ...(data.items ?? [])])
      cursorRef.current = data.next_cursor ?? null
      setHasMore(typeof data.next_cursor === 'string' && data.next_cursor.length > 0)
    } catch (err) {
      // Preserve existing jobs on error — Property 10
      setLoadMoreError(err?.response?.data?.detail ?? err.message ?? 'Failed to load more jobs')
    } finally {
      setLoadingMore(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey, loadingMore])

  return { jobs, setJobs, total, loading, loadingMore, error, loadMoreError, hasMore, loadMore }
}
