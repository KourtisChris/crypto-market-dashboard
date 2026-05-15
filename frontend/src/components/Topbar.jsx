import { useState, useEffect } from 'react'
import { useStore } from '../store'

const BASE = import.meta.env.DEV ? 'http://localhost:8081' : ''

function urlBase64ToUint8Array(base64) {
  const padding = '='.repeat((4 - base64.length % 4) % 4)
  const b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(b64)
  return Uint8Array.from([...raw].map(c => c.charCodeAt(0)))
}

export default function Topbar() {
  const connected    = useStore(s => s.connected)
  const notifEnabled = useStore(s => s.notifEnabled)
  const setNotif     = useStore(s => s.setNotifEnabled)
  const [utc, setUtc] = useState('')

  useEffect(() => {
    const tick = () => {
      const now = new Date()
      const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
      setUtc(`${time} ${tz}`)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  async function toggleNotifications() {
    if (notifEnabled) { setNotif(false); return }
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      alert('Web Push not supported in this browser.')
      return
    }
    try {
      const perm = await Notification.requestPermission()
      if (perm !== 'granted') return
      const keyRes = await fetch(`${BASE}/api/push/vapid-public-key`)
      const { publicKey } = await keyRes.json()
      const reg = await navigator.serviceWorker.register('/sw.js')
      await navigator.serviceWorker.ready
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      })
      const json = sub.toJSON()
      await fetch(`${BASE}/api/push/subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint: sub.endpoint, keys: json.keys }),
      })
      setNotif(true)
    } catch (err) {
      console.error('Push failed:', err)
    }
  }

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="logo">CRYPTO<span>.</span>STATE</div>
        <div className={`live-indicator ${connected ? 'live' : 'offline'}`}>
          <span className="live-dot" />
          {connected ? 'LIVE' : 'RECONNECTING'}
        </div>
      </div>
      <div className="topbar-right">
        <div className="utc-clock">{utc}</div>
        <button
          className={`notif-btn ${notifEnabled ? 'active' : ''}`}
          onClick={toggleNotifications}
        >
          {notifEnabled ? '🔔 ON' : '🔔 Alerts'}
        </button>
      </div>
    </header>
  )
}
