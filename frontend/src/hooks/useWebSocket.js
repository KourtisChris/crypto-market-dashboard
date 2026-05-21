// ============================================================
// src/hooks/useWebSocket.js
// ============================================================
import { useEffect, useRef } from 'react'
import { useStore } from '../store'

// const WS_URL = import.meta.env.DEV
//   ? 'ws://localhost:8081/ws'
//   : `wss://${window.location.host}/ws`
const WS_URL = import.meta.env.DEV
  ? 'ws://localhost:8081/ws'
  : 'wss://crypto-market-dashboard-m5jz.onrender.com/ws'

export function useWebSocket() {
  const ws           = useRef(null)
  const setConnected = useStore(s => s.setConnected)
  const setSnapshot  = useStore(s => s.setSnapshot)
  const setLastAlert = useStore(s => s.setLastAlert)

  useEffect(() => {
    let reconnectTimer = null

    function connect() {
      ws.current = new WebSocket(WS_URL)

      ws.current.onopen = () => {
        setConnected(true)
      }

      ws.current.onmessage = async (e) => {
        const msg = JSON.parse(e.data)
        if (msg.type === 'snapshot') {
          setSnapshot(msg)
        } else if (msg.type === 'state_change') {
          setLastAlert({ ...msg, receivedAt: Date.now() })
          // Refresh history immediately on state change
          const { fetchHistory } = await import('../hooks/useData')
          const store = useStore.getState()
          fetchHistory(msg.tf).then(rows => store.setHistory(msg.tf, rows))
        }
      }

      ws.current.onclose = () => {
        setConnected(false)
        reconnectTimer = setTimeout(connect, 5000)
      }

      ws.current.onerror = () => {
        ws.current?.close()
      }
    }

    connect()
    return () => {
      clearTimeout(reconnectTimer)
      ws.current?.close()
    }
  }, [])
}
