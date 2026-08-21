import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getUnreadCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../api/notifications'

function timeAgo(dateString) {
  const diffMs = Date.now() - new Date(dateString).getTime()
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export default function NotificationBell() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(false)
  const wrapperRef = useRef(null)

  const refreshCount = useCallback(async () => {
    try {
      setUnreadCount(await getUnreadCount())
    } catch {
      // A poll failing silently is fine - the next tick tries again.
    }
  }, [])

  useEffect(() => {
    refreshCount()
    const interval = setInterval(refreshCount, 30000)
    return () => clearInterval(interval)
  }, [refreshCount])

  useEffect(() => {
    if (!open) return undefined
    function handleClickOutside(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  async function togglePanel() {
    const next = !open
    setOpen(next)
    if (next) {
      setLoading(true)
      try {
        const data = await listNotifications()
        setNotifications(data.results)
      } catch {
        setNotifications([])
      } finally {
        setLoading(false)
      }
    }
  }

  async function handleNotificationClick(notification) {
    if (!notification.is_read) {
      try {
        await markNotificationRead(notification.id)
        setNotifications((prev) => prev.map((n) => (n.id === notification.id ? { ...n, is_read: true } : n)))
        setUnreadCount((prev) => Math.max(0, prev - 1))
      } catch {
        // Not critical - the notification just stays marked unread until the next open.
      }
    }
    setOpen(false)
    if (notification.url) navigate(notification.url)
  }

  async function handleMarkAllRead() {
    try {
      await markAllNotificationsRead()
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
      setUnreadCount(0)
    } catch {
      // Leave state as-is - the user can retry.
    }
  }

  return (
    <div className="notif-wrapper" ref={wrapperRef}>
      <button type="button" className="notif-bell" onClick={togglePanel} aria-label="Notifications">
        <svg viewBox="0 0 20 20" fill="none">
          <path
            d="M5 8a5 5 0 0 1 10 0v3.5l1.3 2.2a.6.6 0 0 1-.5.9H4.2a.6.6 0 0 1-.5-.9L5 11.5V8Z"
            stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"
          />
          <path d="M8.2 16a1.8 1.8 0 0 0 3.6 0" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
        {unreadCount > 0 && <span className="notif-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>}
      </button>

      {open && (
        <div className="notif-panel">
          <div className="notif-panel-header">
            <span>Notifications</span>
            {unreadCount > 0 && (
              <button type="button" className="btn-link" onClick={handleMarkAllRead}>
                Mark all as read
              </button>
            )}
          </div>
          <div className="notif-panel-list">
            {loading ? (
              <div className="notif-empty">Loading…</div>
            ) : notifications.length === 0 ? (
              <div className="notif-empty">No notifications yet.</div>
            ) : (
              notifications.map((n) => (
                <button
                  type="button"
                  key={n.id}
                  className={`notif-item ${n.is_read ? '' : 'notif-item-unread'}`}
                  onClick={() => handleNotificationClick(n)}
                >
                  <div className="notif-item-title">{n.title}</div>
                  {n.message && <div className="notif-item-message">{n.message}</div>}
                  <div className="notif-item-meta">
                    {n.company_name ? `${n.company_name} · ` : ''}{timeAgo(n.created_at)}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
