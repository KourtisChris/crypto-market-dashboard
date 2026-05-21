import { useStore } from '../store'
import { typeColor, typeClass, TFS, TF_LABELS, timeAgo } from '../utils'
import { useLatestStates, useConfirmations } from '../hooks/useData'

// % since signal
function calcSinceSignal(stateType, stateLabel, latestState, currentPrices, currentGlobal) {
  if (!stateType || stateType === 'neutral' || !latestState) return null
  const label = (stateLabel || '').toLowerCase()
  let signalPrice = 0, currentPrice = 0, assetName = ''

  if (label.includes('btc long') || label.includes('risk off')) {
    signalPrice = latestState.btc_price || 0
    currentPrice = currentPrices?.BTCUSDT || 0
    assetName = 'BTC'
  } else if (label.includes('eth leading')) {
    signalPrice = latestState.eth_price || 0
    currentPrice = currentPrices?.ETHUSDT || 0
    assetName = 'ETH'
  } else if (label.includes('alts long') || label.includes('late alts') || label.includes('alts short')) {
    signalPrice = latestState.total2_val || 0
    currentPrice = currentGlobal?.total2 || 0
    assetName = 'TOTAL2'
  }

  if (!signalPrice || !currentPrice) return null
  let pct = (currentPrice - signalPrice) / signalPrice * 100
  if (label.includes('alts short') || label.includes('risk off')) pct = -pct
  return { pct: Math.round(pct * 100) / 100, asset: assetName }
}

// Confidence color
function confidenceColor(level) {
  if (level === 'High') return 'rgba(200,205,216,0.4)'
  if (level === 'Medium') return 'rgba(200,205,216,0.4)'
  if (level === 'Low') return 'rgba(200,205,216,0.4)'
  return 'rgba(200,205,216,0.4)'
}

export default function StateCards() {
  const states = useStore(s => s.states)
  const metrics = useStore(s => s.metrics)
  const prices = useStore(s => s.prices)
  const global_ = useStore(s => s.global)
  const latestStates = useLatestStates()
  const confirmations = useConfirmations()

  return (
    <section className="section">
      <div className="section-title">Market State</div>
      <div className="state-grid">
        {TFS.map(tf => {
          const s = states[tf]
          const m = metrics[tf] || {}
          const last = latestStates[tf]

          const cls = s ? typeClass(s.type) : 'neutral'
          const since = s && last
            ? calcSinceSignal(s.type, s.label, last, prices, global_)
            : null

          // Confirmation scores for this TF
          const tfScores = confirmations?.all_scores?.[tf] || []
          const activeSignal = tfScores.find(sc => sc.active)
          const hits = activeSignal?.hits || s?.hits || 0
          const total = activeSignal?.total || s?.total || 0
          const confidence = activeSignal?.confidence || s?.confidence || 'None'
          const confColor = confidenceColor(confidence)

          // Legacy strength bar (activity-based)
          const score = s?.score || 0
          const scoreNorm = Math.min(100, (score * 100) / 5)
          const activity = Math.min(100,
            Math.abs(m.btc_chg || 0) * 5 +
            Math.abs(m.btcd_chg || 0) * 20 +
            Math.abs(m.total2_chg || 0) * 4
          )
          const strength = Math.round(scoreNorm * 0.6 + activity * 0.4)

          return (
            <div key={tf} className={`state-card card ${cls}`}>
              <div className="state-glow" />

              {/* Header */}
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

              {/* Bar 1: Signal strength (activity-based) */}
              <div className="strength-bar">
                <div className="strength-track">
                  <div
                    className="strength-fill"
                    style={{
                      width: `${strength}%`,
                      background: s ? typeColor(s.type) : 'var(--muted)'
                    }}
                  />
                </div>
                <div className="strength-label">{strength}% strength</div>
              </div>

              {/* Bar 2: Confidence (hits/total) */}
              {s && s.type !== 'neutral' && (
                <div className="strength-bar" style={{ marginTop: '6px' }}>
                  <div className="strength-track">
                    <div
                      className="strength-fill"
                      style={{
                        width: total > 0 ? `${(hits / total) * 100}%` : '0%',
                        background: s ? typeColor(s.type) : 'var(--muted)',
                      }}
                    />
                  </div>
                  <div className="strength-label">
                    {total > 0 ? `${hits}/${total} Confirmations` : '—'}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}