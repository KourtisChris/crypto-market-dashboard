import { useState, useEffect } from 'react'
import { useStore } from '../store'
import { useHeatmap } from '../hooks/useData'
import { TFS, TF_LABELS } from '../utils'

const BASE = import.meta.env.DEV
  ? 'http://localhost:8081'
  : 'https://crypto-market-dashboard-m5jz.onrender.com'

const STATE_COLORS = {
  long:     'rgba(57,255,20,0.8)',
  short:    'rgba(255,23,68,0.8)',
  caution:  'rgba(255,171,0,0.8)',
  risk_off: 'rgba(180,0,255,0.75)',
  neutral:  'rgba(202, 204, 207, 0.74)',
}

// Normal view rows
const NORMAL_ROWS = { '1M': 4, '1H': 7, '1D': 6, '1W': 3 }
// Expanded view rows — enough to always have vertical scroll
const EXPANDED_ROWS = { '1M': 72, '1H': 90, '1D': 36, '1W': 10 }

function buildGrid(tf, rawData, totalRows) {
  const map = {}
  for (const row of rawData) {
    const d = new Date(row.period)
    let key
    if (tf === '1M')      key = d.toISOString().slice(0, 16)
    else if (tf === '1H') key = d.toISOString().slice(0, 13)
    else if (tf === '1D') key = d.toISOString().slice(0, 10)
    else                  key = getISOWeek(d)
    map[key] = row
  }
  const now = new Date()

  if (tf === '1M') {
    const cells = [], rowLabels = []
    for (let h = totalRows - 1; h >= 0; h--) {
      const rowCells = []
      const hourDate = new Date(now)
      hourDate.setUTCHours(hourDate.getUTCHours() - h, 0, 0, 0)
      rowLabels.push(hourDate.getUTCHours().toString().padStart(2, '0') + ':00')
      for (let min = 0; min < 60; min++) {
        const d = new Date(hourDate); d.setUTCMinutes(min)
        rowCells.push({ key: d.toISOString().slice(0,16), data: map[d.toISOString().slice(0,16)] || null, isFuture: d > now, ts: d })
      }
      cells.push(rowCells)
    }
    return { cells, rowLabels }
  }

  if (tf === '1H') {
    const cells = [], rowLabels = []
    for (let day = totalRows - 1; day >= 0; day--) {
      const rowCells = []
      const dayDate = new Date(now)
      dayDate.setUTCDate(dayDate.getUTCDate() - day)
      rowLabels.push(dayDate.toUTCString().slice(0, 3) + ' ' + dayDate.getUTCDate())
      for (let h = 0; h < 24; h++) {
        const d = new Date(dayDate); d.setUTCHours(h, 0, 0, 0)
        rowCells.push({ key: d.toISOString().slice(0,13), data: map[d.toISOString().slice(0,13)] || null, isFuture: d > now, ts: d })
      }
      cells.push(rowCells)
    }
    return { cells, rowLabels }
  }

  if (tf === '1D') {
    const cells = [], rowLabels = []
    for (let m = totalRows - 1; m >= 0; m--) {
      const month = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - m, 1))
      rowLabels.push(month.toLocaleString('en', { month: 'short', year: '2-digit', timeZone: 'UTC' }))
      const rowCells = []
      for (let d = 0; d < 30; d++) {
        const day = new Date(month); day.setUTCDate(d + 1)
        rowCells.push({ key: day.toISOString().slice(0,10), data: map[day.toISOString().slice(0,10)] || null, isFuture: day > now, ts: day })
      }
      cells.push(rowCells)
    }
    return { cells, rowLabels }
  }

  // 1W
  const cells = [], rowLabels = []
  const yr = now.getUTCFullYear()
  for (let y = totalRows - 1; y >= 0; y--) {
    const year = yr - y
    rowLabels.push(year.toString())
    const rowCells = []
    for (let w = 1; w <= 52; w++) {
      const weekKey = `${year}-W${w.toString().padStart(2, '0')}`
      const ws = isoWeekToDate(year, w)
      rowCells.push({ key: weekKey, data: map[weekKey] || null, isFuture: ws > now, ts: ws })
    }
    cells.push(rowCells)
  }
  return { cells, rowLabels }
}

function getISOWeek(d) {
  const date = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()))
  date.setUTCDate(date.getUTCDate() + 4 - (date.getUTCDay() || 7))
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1))
  return `${date.getUTCFullYear()}-W${Math.ceil((((date - yearStart) / 86400000) + 1) / 7).toString().padStart(2, '0')}`
}

function isoWeekToDate(year, week) {
  const s = new Date(Date.UTC(year, 0, 1 + (week - 1) * 7))
  const dow = s.getUTCDay()
  if (dow <= 4) s.setUTCDate(s.getUTCDate() - s.getUTCDay() + 1)
  else s.setUTCDate(s.getUTCDate() + 8 - s.getUTCDay())
  return s
}

function formatTooltip(tf, ts, stateLabel) {
  const showTime = tf === '1M' || tf === '1H'
  const dateStr = showTime
    ? ts.toLocaleString([], { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : ts.toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' })
  return stateLabel ? `${stateLabel} | ${dateStr}` : dateStr
}

function HeatmapGrid({ tf, rawData, expanded = false, cellSize = 15 }) {
  const totalRows = expanded ? EXPANDED_ROWS[tf] : NORMAL_ROWS[tf]
  const grid = buildGrid(tf, rawData, totalRows)
  const labelW = expanded ? '44px' : '36px'
  const fontSize = expanded ? '10px' : '9px'

  return (
    <div className="heatmap-grid">
      {grid.cells.map((row, ri) => (
        <div key={ri} className="heatmap-row">
          <div className="heatmap-row-label" style={{ fontSize, width: labelW }}>
            {grid.rowLabels[ri]}
          </div>
          {row.map((cell, ci) => {
            const bg = cell.isFuture ? 'transparent'
              : cell.data ? STATE_COLORS[cell.data.state_type] || STATE_COLORS.neutral
              : 'transparent'
            return (
              <div
                key={ci}
                className="heatmap-cell"
                style={{
                  background: bg,
                  border: !cell.data ? '1px solid rgba(65,64,64,0.61)' : 'none',
                  width: `${cellSize}px`,
                  height: `${cellSize}px`,
                }}
                title={formatTooltip(tf, cell.ts, cell.data?.state_label)}
              />
            )
          })}
        </div>
      ))}
    </div>
  )
}

// Extended intervals for expanded view
const EXT_INTERVALS = {
  '1M': '72 hours',
  '1H': '90 days',
  '1D': '1095 days',
  '1W': '520 weeks',
}

function HeatmapModal({ tf, onClose }) {
  const [extendedData, setExtendedData] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetch(`${BASE}/api/heatmap/${tf}?interval=${encodeURIComponent(EXT_INTERVALS[tf])}`)
      .then(r => r.json())
      .then(d => { setExtendedData(d.data || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [tf])

  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="heatmap-modal-box" onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className="heatmap-modal-header">
          <span className="section-title">Market State Heatmap — {TF_LABELS[tf]}</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        {/* Scrollable grid */}
        <div className="heatmap-modal-content">
          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px' }}>
              <div className="spinner" />
            </div>
          ) : (
            <HeatmapGrid
              tf={tf}
              rawData={extendedData}
              expanded={true}
              cellSize={13}
            />
          )}
        </div>

        {/* Legend */}
        <div className="heatmap-legend" style={{ marginTop: '16px', flexShrink: 0 }}>
          {Object.entries(STATE_COLORS).map(([type, color]) => (
            <div key={type} className="legend-item">
              <div className="legend-dot" style={{ background: color }} />
              <span>{type.replace('_', ' ')}</span>
            </div>
          ))}
          <div className="legend-item">
            <div className="legend-dot" style={{ background: 'transparent', border: '1px solid rgba(65,64,64,0.61)' }} />
            <span>no data</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function Heatmap() {
  const tf      = useStore(s => s.activeTf)
  const setTf   = useStore(s => s.setActiveTf)
  const rawData = useHeatmap(tf)
  const [expanded, setExpanded] = useState(false)

  return (
    <>
      <section className="section">
        <div className="section-header">
          <div className="section-title">Market State Heatmap</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div className="tf-tabs">
              {TFS.map(t => (
                <button key={t} className={`tf-tab ${tf === t ? 'active' : ''}`} onClick={() => setTf(t)}>
                  {TF_LABELS[t]}
                </button>
              ))}
            </div>
            <button
              className="heatmap-expand-btn"
              onClick={() => setExpanded(true)}
              title="Expand heatmap"
            >⛶</button>
          </div>
        </div>

        <div className="card heatmap-card">
          <div className="heatmap-scroll">
            <HeatmapGrid tf={tf} rawData={rawData} />
          </div>
          <div className="heatmap-legend">
            {Object.entries(STATE_COLORS).map(([type, color]) => (
              <div key={type} className="legend-item">
                <div className="legend-dot" style={{ background: color }} />
                <span>{type.replace('_', ' ')}</span>
              </div>
            ))}
            <div className="legend-item">
              <div className="legend-dot" style={{ background: 'transparent', border: '1px solid rgba(65,64,64,0.61)' }} />
              <span>no data</span>
            </div>
          </div>
        </div>
      </section>

      {expanded && <HeatmapModal tf={tf} onClose={() => setExpanded(false)} />}
    </>
  )
}