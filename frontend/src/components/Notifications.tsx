import { useEffect, useState } from 'react'
import { getNotifications, markNotificationRead } from '../api'

interface Notification {
  id: string
  title: string
  body: string
  created_at: string
  read: number
}

export default function Notifications() {
  const [items, setItems] = useState<Notification[]>([])
  const [open, setOpen] = useState(false)

  async function load() {
    try {
      const data = await getNotifications(10)
      setItems(data)
    } catch (e) {
      // ignore
    }
  }

  useEffect(() => {
    void load()
    const t = setInterval(() => void load(), 10000)
    return () => clearInterval(t)
  }, [])

  async function markRead(id: string) {
    try {
      await markNotificationRead(id)
      setItems((s) => s.map((it) => (it.id === id ? { ...it, read: 1 } : it)))
    } catch (e) {
      // ignore
    }
  }

  const unreadCount = items.filter((i) => !i.read).length

  return (
    <div style={{ position: 'fixed', right: 18, top: 18, zIndex: 1200 }}>
      <button
        title="Notificações"
        onClick={() => setOpen(!open)}
        style={{
          background: '#0ea5a4',
          color: 'white',
          borderRadius: 999,
          width: 44,
          height: 44,
          border: 'none',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 6px 18px rgba(2,6,23,0.4)',
        }}
      >
        🔔
        {unreadCount > 0 && (
          <span style={{ marginLeft: 6, fontSize: 12, fontWeight: 700 }}>{unreadCount}</span>
        )}
      </button>

      {open && (
        <div
          style={{
            marginTop: 8,
            width: 360,
            maxHeight: 420,
            overflow: 'auto',
            background: '#0b1220',
            border: '1px solid rgba(148,163,184,0.12)',
            borderRadius: 12,
            padding: 12,
            color: '#e6eef8',
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Notificações</div>
          {items.length === 0 && <div style={{ color: '#9ca3af' }}>Nenhuma notificação</div>}
          {items.map((it) => (
            <div key={it.id} style={{ padding: 8, borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ fontWeight: it.read ? 400 : 700 }}>{it.title}</div>
                <div style={{ color: '#94a3b8', fontSize: 12 }}>{new Date(it.created_at).toLocaleString()}</div>
              </div>
              <div style={{ color: '#cbd5e1', marginTop: 6 }}>{it.body}</div>
              {!it.read && (
                <div style={{ marginTop: 8 }}>
                  <button
                    className="btn-screen"
                    onClick={() => void markRead(it.id)}
                    style={{ fontSize: 13 }}
                  >
                    Marcar como lida
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
