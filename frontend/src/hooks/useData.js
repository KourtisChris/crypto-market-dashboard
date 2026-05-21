// ============================================================
// src/hooks/useData.js — API data fetching
// ============================================================
import { useEffect, useState } from 'react'
import { useStore } from '../store'

const BASE = import.meta.env.DEV
  ? 'http://localhost:8081'
  : 'https://crypto-market-dashboard-m5jz.onrender.com'

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

export async function fetchConfirmations() {
  const r = await fetch(`${BASE}/api/confirmations`)
  if (!r.ok) return null
  return r.json()
}

export function useHistory(tf) {
  const history    = useStore(s => s.history[tf])
  const setHistory = useStore(s => s.setHistory)
  useEffect(() => {
    fetchHistory(tf).then(rows => setHistory(tf, rows))
    const id = setInterval(() => {
      fetchHistory(tf).then(rows => setHistory(tf, rows))
    }, 60000)
    return () => clearInterval(id)
  }, [tf])
  return history
}

export function useHeatmap(tf) {
  const heatmap    = useStore(s => s.heatmap[tf])
  const setHeatmap = useStore(s => s.setHeatmap)
  useEffect(() => {
    fetchHeatmap(tf).then(rows => setHeatmap(tf, rows))
    const id = setInterval(() => {
      fetchHeatmap(tf).then(rows => setHeatmap(tf, rows))
    }, 60000)
    return () => clearInterval(id)
  }, [tf])
  return heatmap
}

export function useLatestStates() {
  const [latestStates, setLatestStates] = useState({})
  useEffect(() => {
    fetchLatestStates().then(setLatestStates)
    const id = setInterval(() => fetchLatestStates().then(setLatestStates), 60000)
    return () => clearInterval(id)
  }, [])
  return latestStates
}

// Hook: fetch confirmations every 60s
export function useConfirmations() {
  const confirmations    = useStore(s => s.confirmations)
  const setConfirmations = useStore(s => s.setConfirmations)
  useEffect(() => {
    fetchConfirmations().then(setConfirmations)
    const id = setInterval(() => fetchConfirmations().then(setConfirmations), 60000)
    return () => clearInterval(id)
  }, [])
  return confirmations
}