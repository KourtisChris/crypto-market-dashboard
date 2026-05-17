import { useStore } from '../store'
import { typeColor, typeClass, TFS, TF_LABELS, timeAgo } from '../utils'
import { useLatestStates } from '../hooks/useData'

// Thresholds per TF — same as backend config
const THRESHOLDS = {
  '1M': { btc: 0.08,  btcd: 0.015, total2: 0.10, ethbtc: 0.06 },
  '1H': { btc: 0.5,   btcd: 0.12,  total2: 0.6,  ethbtc: 0.4  },
  '1D': { btc: 1.5,   btcd: 0.25,  total2: 2.0,  ethbtc: 1.25 },
  '1W': { btc: 3.5,   btcd: 0.5,   total2: 4.0,  ethbtc: 2.0  },
}

// ============================================================
// Calculate % distance from trigger for the primary metric
// of the current state type.
//
// Long states  (long, caution):  positive = above trigger (good)
// Short states (short, risk_off): positive = below trigger (good)
// ============================================================
function calcTriggerDistance(stateType, m, tf) {
  if (!m || !stateType || stateType === 'neutral') return null
  const thr = THRESHOLDS[tf]
  if (!thr) return null

  switch (stateType) {
    case 'long':
    case 'caution': {
      // Primary metric: how far BTC.D has dropped below its threshold
      // btcd_chg < -thr.btcd means dominance is falling (bullish for alts)
      const dist = -(m.btcd_chg || 0) - thr.btcd
      return { value: dist, primary: 'BTC.D' }
    }
    case 'short': {
      // Primary metric: how far BTC has dropped below its threshold
      const dist = -(m.btc_chg || 0) - thr.btc
      return { value: dist, primary: 'BTC' }
    }
    case 'risk_off': {
      // Primary metric: how far total2 has dropped below its threshold
      const dist = -(m.total2_chg || 0) - thr.total2
      return { value: dist, primary: 'TOTAL2' }
    }
    default:
      return null
  }
}

function formatTrigger(dist, stateType) {
  if (!dist) return null
  const val = dist.value
  const sign = val >= 0 ? '+' : ''
  const isLong = stateType === 'long' || stateType === 'caution'
  const color = (isLong && val >= 0) || (!isLong && val >= 0)
    ? 'var(--bull)'
    : 'var(--bear)'
  return { text: `${sign}${val.toFixed(2)}% from trigger`, color }
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
          const dist       = s ? calcTriggerDistance(s.type, m, tf) : null
          const trigger    = dist ? formatTrigger(dist, s.type) : null

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

              {/* % distance from trigger */}
              {s && (
                <div className="state-score">
                  {trigger ? trigger.text : `×${score.toFixed(1)} from trigger`}
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
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
