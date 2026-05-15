// ============================================================
// src/utils.js — shared formatting & color helpers
// ============================================================

export const TF_LABELS = {
  '1M': '1 Minute',
  '1H': '1 Hour',
  '1D': '1 Day',
  '1W': '1 Week',
}

export const TFS = ['1M', '1H', '1D', '1W']

export const fmt = (v, d = 2) => {
  if (v == null) return 'N/A'
  return (v >= 0 ? '+' : '') + v.toFixed(d) + '%'
}

export const fmtPrice = (v) => {
  if (!v) return '—'
  if (v >= 1000) return '$' + v.toLocaleString('en', { maximumFractionDigits: 0 })
  if (v >= 1)    return '$' + v.toFixed(2)
  return '$' + v.toFixed(4)
}

export const fmtBig = (v) => {
  if (!v) return '—'
  if (v >= 1e12) return '$' + (v / 1e12).toFixed(2) + 'T'
  if (v >= 1e9)  return '$' + (v / 1e9).toFixed(1) + 'B'
  return '$' + v.toLocaleString()
}

export const typeColor = (type) => ({
  long:     '#39ff14',
  short:    '#ff1744',
  caution:  '#ffab00',
  risk_off: '#b000ff',
  neutral:  'rgba(200,205,216,0.5)',
}[type] || 'rgba(200,205,216,0.5)')

export const typeClass = (type) => ({
  long:     'bullish',
  short:    'bearish',
  caution:  'caution',
  risk_off: 'risk-off',
  neutral:  'neutral',
}[type] || 'neutral')

// Formats time elapsed since a given ISO timestamp
// e.g. "17m ago", "2d 3h ago", "just now"
export function timeAgo(iso) {
  if (!iso) return ''
  const sec = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (sec < 10)    return 'just now'
  if (sec < 60)    return `${sec}s ago`
  const min = Math.floor(sec / 60)
  if (min < 60)    return `${min}m ago`
  const hr  = Math.floor(min / 60)
  const remMin = min % 60
  if (hr < 24)     return remMin > 0 ? `${hr}h ${remMin}m ago` : `${hr}h ago`
  const day = Math.floor(hr / 24)
  const remHr = hr % 24
  if (remHr > 0)   return `${day}d ${remHr}h ago`
  return `${day}d ago`
}
