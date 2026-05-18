import { create } from 'zustand'

export const useStore = create((set) => ({
  connected:    false,
  setConnected: (v) => set({ connected: v }),

  prices:    {},
  global:    {},
  states:    {},
  metrics:   {},
  topMovers: {},
  timestamp: null,

  setSnapshot: (snap) => set({
    prices:    snap.prices     || {},
    global:    snap.global     || {},
    states:    snap.states     || {},
    metrics:   snap.metrics    || {},
    topMovers: snap.top_movers || {},
    timestamp: snap.timestamp,
  }),

  history: { '1M': [], '1H': [], '1D': [], '1W': [] },
  heatmap: { '1M': [], '1H': [], '1D': [], '1W': [] },

  setHistory: (tf, rows) => set(s => ({ history: { ...s.history, [tf]: rows } })),
  setHeatmap: (tf, rows) => set(s => ({ heatmap: { ...s.heatmap, [tf]: rows } })),

  lastAlert:    null,
  setLastAlert: (alert) => set({ lastAlert: alert }),

  activeTf:    '1H',
  setActiveTf: (tf) => set({ activeTf: tf }),

  notifEnabled:    false,
  setNotifEnabled: (v) => set({ notifEnabled: v }),

  // Confirmation data (per-tf signal scores + raw indicators)
  confirmations: null,
  setConfirmations: (data) => set({ confirmations: data }),
}))