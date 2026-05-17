import { useStore } from '../store'
import { typeColor, typeClass, TFS, TF_LABELS, timeAgo } from '../utils'
import { useLatestStates } from '../hooks/useData'

// ============================================================
// % change since signal — shows how much the primary asset
// has moved since the signal was triggered
//
// BTC Long     → % change of BTC price since signal
// Alts Long    → % change of TOTAL2 since signal
// ETH Leading  → % change of ETH price since signal
// Late Alts    → % change of TOTAL2 since signal
// Alts Short   → % change of TOTAL2 since signal (inverted)
// Risk Off     → % change of BTC price since signal
// ============================================================
function calcSinceSignal(stateType, stateLabel, latestState, currentPrices, currentGlobal) {
  if (!stateType || stateType === 'neutral' || !latestState) return null

  const label = (stateLabel || '').toLowerCase()

  // Determine which asset to track and its signal-time price
  let signalPrice = 0
  let currentPrice = 0
  let assetName = ''

  if (label.includes('btc long') || label.includes('risk off')) {
    signalPrice  = latestState.btc_price || 0
    currentPrice = currentPrices?.BTCUSDT || 0
    assetName    = 'BTC'
  } else if (label.includes('eth leading')) {
    signalPrice  = latestState.eth_price || 0
    currentPrice = currentPrices?.ETHUSDT || 0
    assetName    = 'ETH'
  } else if (
    label.includes('alts long') ||
    label.includes('late alts') ||
    label.includes('alts short')
  ) {
    signalPrice  = latestState.total2_val || 0
    currentPrice = currentGlobal?.total2 || 0
    assetName    = 'TOTAL2'
  }

  if (!signalPrice || !currentPrice) return null

  let pct = (currentPrice - signalPrice) / signalPrice * 100

  // For short signals, invert: price going down is positive (good)
  if (label.includes('alts short') || label.includes('risk off')) {
    pct = -pct
  }

  return { pct: round2(pct), asset: assetName }
}

function round2(v) {
  return Math.round(v * 100) / 100
}

// Confidence bar
function calcConfidence(score, m) {
  if (!m) return 0
  const scoreNorm = Math.min(100, (score * 100) / 5)
  const activity  = Math.min(100,
    Math.abs(m.btc_chg    || 0) * 5  +
    Math.abs(m.btcd_chg   || 0) * 20 +
    Math.abs(m.total2_chg || 0) * 4
  )
  return Math.round(scoreNorm * 0.6 + activity * 0.4)
}

export default function StateCards() {
  const states       = useStore(s => s.states)
  const metrics      = useStore(s => s.metrics)
  const prices       = useStore(s => s.prices)
  const global_      = useStore(s => s.global)
  const latestStates = useLatestStates()

  return (
    <section className="section">
      <div className="section-title">Market State</div>
      <div className="state-grid">
        {TFS.map(tf => {
          const s    = states[tf]
          const m    = metrics[tf] || {}
          const last = latestStates[tf]

          const score      = s?.score || 0
          const confidence = s ? calcConfidence(score, m) : 0
          const cls        = s ? typeClass(s.type) : 'neutral'

          const since = s && last
            ? calcSinceSignal(s.type, s.label, last, prices, global_)
            : null

          return (
            <div key={tf} className={`state-card card ${cls}`}>
              <div className="state-glow" />

              {/* Header: TF label + time ago */}
              <div className="state-card-header">
                <div className="state-tf">{TF_LABELS[tf]}</div>
                {last?.recorded_at && (
                  <div className="state-card-ago">{timeAgo(last.recorded_at)}</div>
                )}
              </div>

              {/* State label */}
              <div className="state-label">
                {s ? `${s.emoji} ${s.label}` : '—'}
              </div>

              {/* % since signal */}
              {s && (
                <div className="state-score">
                  {since
                    ? `${since.asset}: ${since.pct >= 0 ? '+' : ''}${since.pct.toFixed(2)}% since signal`
                    : '—'
                  }
                </div>
              )}

              {/* Confidence bar */}
              <div className="strength-bar">
                <div className="strength-track">
                  <div
                    className="strength-fill"
                    style={{
                      width: `${confidence}%`,
                      background: s ? typeColor(s.type) : 'var(--muted)'
                    }}
                  />
                </div>
                <div className="strength-label">
                  {confidence}% strength
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}