import { useStore } from '../store'
import { fmt, TFS, TF_LABELS } from '../utils'

function CoinRow({ coin, index }) {
  const btcDir = coin.altbtc_chg >= 0 ? 'up' : 'down'
  const t2Dir  = coin.vs_total2  >= 0 ? 'up' : 'down'
  const sym    = coin.symbol.replace('USDT', '')
  return (
    <div className="mover-row">
      <span className="mover-rank">#{index + 1}</span>
      <span className="mover-symbol">
        {sym}
        {coin.hidden_signal === 'hidden_strength' && <span className="hidden-tag" title="Hidden strength">✨</span>}
        {coin.hidden_signal === 'hidden_weakness'  && <span className="hidden-tag" title="Hidden weakness">⚠️</span>}
      </span>
      <div className="mover-vals">
        <div className={`mover-val ${btcDir}`}>{fmt(coin.altbtc_chg)}<small>vs BTC</small></div>
        <div className={`mover-val ${t2Dir}`}>{fmt(coin.vs_total2)}<small>vs T2</small></div>
      </div>
    </div>
  )
}

export default function TopMovers() {
  const tf     = useStore(s => s.activeTf)
  const setTf  = useStore(s => s.setActiveTf)
  const movers = useStore(s => s.topMovers[tf]) || { strong: [], weak: [] }

  return (
    <section className="section">
      <div className="section-header">
        <div className="section-title">Top Movers</div>
        <div className="tf-tabs">
          {TFS.map(t => (
            <button key={t} className={`tf-tab ${tf === t ? 'active' : ''}`} onClick={() => setTf(t)}>
              {TF_LABELS[t]}
            </button>
          ))}
        </div>
      </div>
      <div className="movers-grid">
        <div className="card">
          <div className="movers-header strong">📈 Top Strong</div>
          <div className="movers-list">
            {movers.strong.length
              ? movers.strong.map((c, i) => <CoinRow key={c.symbol} coin={c} index={i} />)
              : <div className="empty-state">No data yet</div>}
          </div>
        </div>
        <div className="card">
          <div className="movers-header weak">📉 Top Weak</div>
          <div className="movers-list">
            {movers.weak.length
              ? movers.weak.map((c, i) => <CoinRow key={c.symbol} coin={c} index={i} />)
              : <div className="empty-state">No data yet</div>}
          </div>
        </div>
      </div>
    </section>
  )
}
