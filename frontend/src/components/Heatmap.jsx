import { useStore } from '../store'
import { useHeatmap } from '../hooks/useData'
import { TFS, TF_LABELS } from '../utils'

const STATE_COLORS = {
  long:     'rgba(57,255,20,0.8)',
  short:    'rgba(255,23,68,0.8)',
  caution:  'rgba(255,171,0,0.8)',
  risk_off: 'rgba(180,0,255,0.75)',
  neutral:  'rgba(200,205,216,0.25)',
}

function buildGrid(tf, rawData) {
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
    for (let h = 3; h >= 0; h--) {
      const rowCells = []
      const hourDate = new Date(now)
      hourDate.setUTCHours(hourDate.getUTCHours() - h, 0, 0, 0)
      rowLabels.push(hourDate.getUTCHours().toString().padStart(2,'0') + ':00')
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
    for (let day = 6; day >= 0; day--) {
      const rowCells = []
      const dayDate = new Date(now)
      dayDate.setUTCDate(dayDate.getUTCDate() - day)
      rowLabels.push(dayDate.toUTCString().slice(0, 3))
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
    for (let m = 5; m >= 0; m--) {
      const month = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - m, 1))
      rowLabels.push(month.toLocaleString('en', { month: 'short', timeZone: 'UTC' }))
      const rowCells = []
      for (let d = 0; d < 30; d++) {
        const day = new Date(month); day.setUTCDate(d + 1)
        rowCells.push({ key: day.toISOString().slice(0,10), data: map[day.toISOString().slice(0,10)] || null, isFuture: day > now, ts: day })
      }
      cells.push(rowCells)
    }
    return { cells, rowLabels }
  }

  const cells = [], rowLabels = []
  const yr = now.getUTCFullYear()
  for (let y = 2; y >= 0; y--) {
    const year = yr - y; rowLabels.push(year.toString())
    const rowCells = []
    for (let w = 1; w <= 52; w++) {
      const weekKey = `${year}-W${w.toString().padStart(2,'0')}`
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
  return `${date.getUTCFullYear()}-W${Math.ceil((((date - yearStart) / 86400000) + 1) / 7).toString().padStart(2,'0')}`
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

export default function Heatmap() {
  const tf      = useStore(s => s.activeTf)
  const setTf   = useStore(s => s.setActiveTf)
  const rawData = useHeatmap(tf)
  const grid    = buildGrid(tf, rawData)

  return (
    <section className="section">
      <div className="section-header">
        <div className="section-title">Market State Heatmap</div>
        <div className="tf-tabs">
          {TFS.map(t => (
            <button key={t} className={`tf-tab ${tf === t ? 'active' : ''}`} onClick={() => setTf(t)}>
              {TF_LABELS[t]}
            </button>
          ))}
        </div>
      </div>
      <div className="card heatmap-card">
        <div className="heatmap-scroll">
          <div className="heatmap-grid">
            {grid.cells.map((row, ri) => (
              <div key={ri} className="heatmap-row">
                <div className="heatmap-row-label">{grid.rowLabels[ri]}</div>
                {row.map((cell, ci) => {
                  const bg = cell.isFuture ? 'rgba(255,255,255,0.03)'
                    : cell.data ? STATE_COLORS[cell.data.state_type] || STATE_COLORS.neutral
                    : 'rgba(255,255,255,0.06)'
                  return (
                    <div key={ci} className="heatmap-cell" style={{ background: bg }}
                      title={formatTooltip(tf, cell.ts, cell.data?.state_label)} />
                  )
                })}
              </div>
            ))}
          </div>
        </div>
        <div className="heatmap-legend">
          {Object.entries(STATE_COLORS).map(([type, color]) => (
            <div key={type} className="legend-item">
              <div className="legend-dot" style={{ background: color }} />
              <span>{type.replace('_', ' ')}</span>
            </div>
          ))}
          <div className="legend-item">
            <div className="legend-dot" style={{ background: 'rgba(255,255,255,0.06)' }} />
            <span>no data</span>
          </div>
        </div>
      </div>
    </section>
  )
}
