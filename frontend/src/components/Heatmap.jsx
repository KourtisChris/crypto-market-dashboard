import { useState, useRef, useEffect } from 'react'
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

// ---- Grid builders ----
function buildGrid(tf, rawData, expanded = false, offsetRows = 0) {
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
    const totalRows = expanded ? 24 : 4
    const cells = [], rowLabels = []
    for (let h = totalRows - 1 + offsetRows; h >= offsetRows; h--) {
      const rowCells = []
      const hourDate = new Date(now)
      hourDate.setUTCHours(hourDate.getUTCHours() - h, 0, 0, 0)
      rowLabels.push(hourDate.getUTCHours().toString().padStart(2,'00') + ':00')
      for (let min = 0; min < 60; min++) {
        const d = new Date(hourDate); d.setUTCMinutes(min)
        rowCells.push({ key: d.toISOString().slice(0,16), data: map[d.toISOString().slice(0,16)] || null, isFuture: d > now, ts: d })
      }
      cells.push(rowCells)
    }
    return { cells, rowLabels }
  }

  if (tf === '1H') {
    const totalRows = expanded ? 30 : 7
    const cells = [], rowLabels = []
    for (let day = totalRows - 1 + offsetRows; day >= offsetRows; day--) {
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
    const totalMonths = expanded ? 12 : 6
    const cells = [], rowLabels = []
    for (let m = totalMonths - 1 + offsetRows; m >= offsetRows; m--) {
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
  const totalYears = expanded ? 5 : 3
  const cells = [], rowLabels = []
  const yr = now.getUTCFullYear()
  for (let y = totalYears - 1 + offsetRows; y >= offsetRows; y--) {
    const year = yr - y; rowLabels.push(year.toString())
    const rowCells = []
    for (let w = 1; w <= 52; w++) {
      const weekKey = `${year}-W${w.toString().padStart(2,'00')}`
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
  return `${date.getUTCFullYear()}-W${Math.ceil((((date - yearStart) / 86400000) + 1) / 7).toString().padStart(2,'00')}`
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

// Max offset per TF (how far back you can scroll)
const MAX_OFFSET = { '1M': 48, '1H': 60, '1D': 24, '1W': 10 }

// ---- HeatmapGrid component (reusable) ----
function HeatmapGrid({ tf, rawData, expanded = false, offsetRows = 0, cellSize = 15 }) {
  const grid = buildGrid(tf, rawData, expanded, offsetRows)
  return (
    <div className="heatmap-grid">
      {grid.cells.map((row, ri) => (
        <div key={ri} className="heatmap-row">
          <div className="heatmap-row-label" style={{ fontSize: expanded ? '10px' : '9px', width: expanded ? '44px' : '36px' }}>
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

// ---- Expanded Modal ----
function HeatmapModal({ tf, onClose }) {
  const [extendedData, setExtendedData] = useState([])
  const [loading, setLoading] = useState(true)

  // Extended intervals for expanded view
  const extIntervals = { '1M': '72 hours', '1H': '90 days', '1D': '540 days', '1W': '520 weeks' }

  useEffect(() => {
    setLoading(true)
    fetch(`${BASE}/api/heatmap/${tf}?interval=${encodeURIComponent(extIntervals[tf])}`)
      .then(r => r.json())
      .then(d => { setExtendedData(d.data || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [tf])

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="heatmap-modal-box"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="heatmap-modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span className="section-title">Market State Heatmap — {TF_LABELS[tf]}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button className="modal-close" onClick={onClose}>✕</button>
          </div>
        </div>

        {/* Grid */}
        <div className="heatmap-modal-content">
          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px' }}>
              <div className="spinner" />
            </div>
          ) : (
            <div className="heatmap-scroll">
              <HeatmapGrid
                tf={tf}
                rawData={extendedData}
                expanded={true}
                offsetRows={offsetRows}
                cellSize={13}
              />
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="heatmap-legend" style={{ marginTop: '16px' }}>
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

// ---- Main Heatmap component ----
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