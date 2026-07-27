import { useRef, useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Bell, BrainCircuit, Briefcase, CheckCheck } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNotifications } from '@/hooks/useNotifications'
import { cn } from '@/lib/utils'

const TYPE_ICON = {
  NEW_JOB_MATCHES: BrainCircuit,
  NEW_CANDIDATE_MATCHES: BrainCircuit,
  APPLICATION_STATUS: Briefcase,
}

function NotificationItem({ notification, onRead }) {
  const Icon = TYPE_ICON[notification.type] ?? Bell
  const isUnread = !notification.read_at

  const handleClick = () => {
    if (isUnread) onRead(notification.id)
  }

  const inner = (
    <div
      onClick={handleClick}
      className={cn(
        'flex items-start gap-3 px-4 py-3 hover:bg-surface-muted transition-colors cursor-pointer',
        isUnread && 'bg-brand-blue/5'
      )}
    >
      <div className={cn('w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5', isUnread ? 'bg-brand-blue/15' : 'bg-gray-100')}>
        <Icon size={13} className={isUnread ? 'text-brand-blue' : 'text-text-muted'} />
      </div>
      <div className="flex-1 min-w-0">
        <p className={cn('text-xs leading-snug', isUnread ? 'font-semibold text-text' : 'text-text-muted')}>
          {notification.title}
        </p>
        {notification.body && (
          <p className="text-[11px] text-text-muted mt-0.5 truncate">{notification.body}</p>
        )}
        <p className="text-[10px] text-text-muted mt-1">
          {new Date(notification.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
        </p>
      </div>
      {isUnread && <span className="w-1.5 h-1.5 rounded-full bg-brand-blue flex-shrink-0 mt-1.5" aria-hidden="true" />}
    </div>
  )

  // If it links to a job, wrap with Link
  if (notification.entity_type === 'JOB' && notification.type === 'NEW_JOB_MATCHES') {
    return <Link to="/candidate/matches">{inner}</Link>
  }
  return inner
}

export default function NotificationBell() {
  const { notifications, unreadCount, loading, markRead, markAllRead } = useNotifications()
  const [open, setOpen] = useState(false)
  const wrapperRef = useRef(null)

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={wrapperRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative p-1.5 rounded-md text-text-muted hover:text-brand-blue hover:bg-surface-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
        aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}
        aria-expanded={open}
        aria-haspopup="true"
      >
        <Bell size={18} />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-brand-amber text-white text-[9px] font-bold flex items-center justify-center leading-none">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            className="absolute right-0 top-full mt-2 w-80 bg-white rounded-xl shadow-lg border border-border z-50 overflow-hidden"
            role="dialog"
            aria-label="Notifications"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h3 className="text-sm font-semibold text-text">Notifications</h3>
              {unreadCount > 0 && (
                <button
                  onClick={markAllRead}
                  className="flex items-center gap-1 text-[11px] text-brand-blue hover:underline focus-visible:outline-none"
                >
                  <CheckCheck size={12} /> Mark all read
                </button>
              )}
            </div>

            {/* List */}
            <div className="max-h-80 overflow-y-auto divide-y divide-border">
              {loading && (
                <div className="flex items-center justify-center py-8">
                  <div className="w-5 h-5 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
                </div>
              )}
              {!loading && notifications.length === 0 && (
                <p className="text-xs text-text-muted text-center py-8">No notifications yet</p>
              )}
              {!loading && notifications.map((n) => (
                <NotificationItem key={n.id} notification={n} onRead={markRead} />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
