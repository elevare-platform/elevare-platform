import { useState, useEffect, useCallback } from 'react'
import api from '@/lib/api'
import { useAuth } from '@/context/AuthContext'

/**
 * useNotifications - fetches in-app notifications for the current user on load.
 *
 * No WebSocket / polling - v1 delivers "new matches waiting" on next page open.
 * Exposes markRead / markAllRead so the bell UI can update without a refetch.
 */
export function useNotifications() {
  const { user } = useAuth()
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(false)

  const fetchNotifications = useCallback(async () => {
    if (!user) return
    setLoading(true)
    try {
      const [listRes, countRes] = await Promise.all([
        api.get('/api/v1/notifications', { params: { limit: 20 } }),
        api.get('/api/v1/notifications/unread-count'),
      ])
      setNotifications(listRes.data.items ?? [])
      setUnreadCount(countRes.data.count ?? 0)
    } catch {
      // silently ignore - non-critical
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => {
    fetchNotifications()
  }, [fetchNotifications])

  const markRead = useCallback(async (id) => {
    try {
      await api.patch(`/api/v1/notifications/${id}/read`)
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n))
      )
      setUnreadCount((c) => Math.max(0, c - 1))
    } catch { /* ignore */ }
  }, [])

  const markAllRead = useCallback(async () => {
    try {
      await api.patch('/api/v1/notifications/read-all')
      setNotifications((prev) => prev.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })))
      setUnreadCount(0)
    } catch { /* ignore */ }
  }, [])

  return { notifications, unreadCount, loading, markRead, markAllRead, refetch: fetchNotifications }
}
