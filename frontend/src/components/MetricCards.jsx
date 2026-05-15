import { useStore } from '../store'
import { fmt, fmtPrice, fmtBig, TFS, TF_LABELS } from '../utils'

export default function MetricCards() {
  const prices   = useStore(s => s.prices)
  const global_  = useStore(s => s.global)
  const metrics  = useStore(s => s.metrics)
  const activeTf = useStore(s => s.activeTf)
  const setTf    = useStore(s => s.setActiveTf)
  const m        = metrics[activeTf] || {}

  const cards = [
    { label: 'BTC Price',     value: fmtPrice(prices.BTCUSDT),             change: m.btc_chg,    sub: 'BTCUSDT' },
    { label: 'BTC Dominance', value: `${(global_.btcd || 0).toFixed(2)}%`, change: m.btcd_chg,   sub: 'BTC.D' },
    { label: 'TOTAL2',        value: fmtBig(global_.total2),               change: m.total2_chg, sub: 'ex-BTC market cap' },
    { label: 'ETH / BTC',     value: (prices.ETHBTC || 0).toFixed(4),      change: m.ethbtc_chg, sub: 'ETHBTC ratio' },
  ]

  return (
    <section className="section">
      <div className="section-header">
        <div className="section-title">Key Metrics</div>
        <div className="tf-tabs">
          {TFS.map(tf => (
            <button key={tf} className={`tf-tab ${activeTf === tf ? 'active' : ''}`} onClick={() => setTf(tf)}>
              {TF_LABELS[tf]}
            </button>
          ))}
        </div>
      </div>
      <div className="metric-grid">
        {cards.map(c => {
          const dir = (c.change > 0.01) ? 'up' : (c.change < -0.01) ? 'down' : 'flat'
          return (
            <div key={c.label} className="card metric-card">
              <div className="metric-label">{c.label}</div>
              <div className="metric-value">{c.value}</div>
              <div className={`metric-change ${dir}`}>
                {fmt(c.change)} <span className="metric-tf">({TF_LABELS[activeTf]})</span>
              </div>
              <div className="metric-sub">{c.sub}</div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
