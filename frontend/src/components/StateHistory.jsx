import { useStore } from '../store'
import { useHistory } from '../hooks/useData'
import { typeColor, fmt, TFS, TF_LABELS, timeAgo } from '../utils'

export default function StateHistory() {
  const tf    = useStore(s => s.activeTf)
  const setTf = useStore(s => s.setActiveTf)
  const rows  = useHistory(tf)

  return (
    <section className="section">
      <div className="section-header">
        <div className="section-title">State History</div>
        <div className="tf-tabs">
          {TFS.map(t => (
            <button key={t} className={`tf-tab ${tf === t ? 'active' : ''}`} onClick={() => setTf(t)}>
              {TF_LABELS[t]}
            </button>
          ))}
        </div>
      </div>
      <div className="card history-card">
        <div className="history-list">
          {rows.length === 0 && <div className="empty-state">No history yet — starts recording from now</div>}
          {rows.slice(0, 30).map(r => (
            <div key={r.id} className="history-item">
              <div className="history-state-dot" style={{ background: typeColor(r.state_type) }} />
              <div className="history-body">
                <div className="history-label" style={{ color: typeColor(r.state_type) }}>{r.state_label}</div>
                <div className="history-metrics">
                  <span>BTC {fmt(r.btc_chg)}</span>
                  <span>BTC.D {fmt(r.btcd_chg)}</span>
                  <span>T2 {fmt(r.total2_chg)}</span>
                  <span className="history-score">score {(r.score * 100).toFixed(0)}</span>
                </div>
              </div>
              <div className="history-time">{timeAgo(r.recorded_at)}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
