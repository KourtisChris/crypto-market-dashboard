// ============================================================
// src/hooks/useData.js — API data fetching
// ============================================================
import { useEffect, useState } from 'react'
import { useStore } from '../store'

const BASE = import.meta.env.DEV ? 'http://localhost:8081' : ''

export async function fetchHistory(tf) {
  const r = await fetch(`${BASE}/api/history/${tf}?limit=100`)
  if (!r.ok) return []
  const d = await r.json()
  return d.history || []
}

export async function fetchHeatmap(tf) {
  const r = await fetch(`${BASE}/api/heatmap/${tf}`)
  if (!r.ok) return []
  const d = await r.json()
  return d.data || []
}

export async function fetchSnapshot() {
  const r = await fetch(`${BASE}/api/snapshot`)
  if (!r.ok) throw new Error('snapshot ' + r.status)
  return r.json()
}

export async function fetchLatestStates() {
  const r = await fetch(`${BASE}/api/latest-states`)
  if (!r.ok) return {}
  return r.json()
}

// Hook: load history when tf changes
export function useHistory(tf) {
  const history    = useStore(s => s.history[tf])
  const setHistory = useStore(s => s.setHistory)
  useEffect(() => {
    if (!history.length) {
      fetchHistory(tf).then(rows => setHistory(tf, rows))
    }
  }, [tf])
  return history
}

// Hook: load heatmap when tf changes
export function useHeatmap(tf) {
  const heatmap    = useStore(s => s.heatmap[tf])
  const setHeatmap = useStore(s => s.setHeatmap)
  useEffect(() => {
    if (!heatmap.length) {
      fetchHeatmap(tf).then(rows => setHeatmap(tf, rows))
    }
  }, [tf])
  return heatmap
}

// Hook: latest state timestamps per TF (refreshes every 60s)
export function useLatestStates() {
  const [latestStates, setLatestStates] = useState({})
  useEffect(() => {
    fetchLatestStates().then(setLatestStates)
    const id = setInterval(() => fetchLatestStates().then(setLatestStates), 60000)
    return () => clearInterval(id)
  }, [])
  return latestStates
}
