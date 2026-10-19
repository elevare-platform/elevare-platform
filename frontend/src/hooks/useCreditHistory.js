import { useState, useEffect, useCallback, useRef } from 'react'
import api from '@/lib/api'

/**
 * useCreditHistory - the organization's credit history, newest first, a page at a
 * time (GET /api/v1/credits/transactions).
 *
 * `loadMore` appends the next page; `reload` starts again from the newest.
 */
export function useCreditHistory(pageSize = 20) {
  const [items, setItems] = useState([])
  const [nextCursor, setNextCursor] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(null)
  // Ignore an answer that arrives after a newer request was made (a quick reload).
  const requestId = useRef(0)

  const fetchPage = useCallback(async (cursor) => {
    const params = { limit: pageSize }
    if (cursor) params.cursor = cursor
    const { data } = await api.get('/api/v1/credits/transactions', { params })
    return data
  }, [pageSize])

  const reload = useCallback(async () => {
    const id = ++requestId.current
    setLoading(true)
    setError(null)
    try {
      const data = await fetchPage(null)
      if (id !== requestId.current) return
      setItems(data.items)
      setNextCursor(data.next_cursor)
    } catch {
      if (id !== requestId.current) return
      setError('We could not load your credit history.')
    } finally {
      if (id === requestId.current) setLoading(false)
    }
  }, [fetchPage])

  const loadMore = useCallback(async () => {
    if (!nextCursor) return
    const id = ++requestId.current
    setLoadingMore(true)
    setError(null)
    try {
      const data = await fetchPage(nextCursor)
      if (id !== requestId.current) return
      setItems((current) => [...current, ...data.items])
      setNextCursor(data.next_cursor)
    } catch {
      if (id !== requestId.current) return
      setError('We could not load more of your credit history.')
    } finally {
      if (id === requestId.current) setLoadingMore(false)
    }
  }, [fetchPage, nextCursor])

  // The first page. State is only set once the answer arrives (`loading` starts
  // true), and a page that comes back after the screen is gone is ignored.
  useEffect(() => {
    let cancelled = false
    fetchPage(null)
      .then((data) => {
        if (cancelled) return
        setItems(data.items)
        setNextCursor(data.next_cursor)
        setLoading(false)
      })
      .catch(() => {
        if (cancelled) return
        setError('We could not load your credit history.')
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [fetchPage])

  return { items, hasMore: Boolean(nextCursor), loading, loadingMore, error, loadMore, reload }
}
