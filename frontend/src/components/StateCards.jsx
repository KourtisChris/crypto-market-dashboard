import { useStore } from '../store'
import { typeColor, typeClass, TFS, TF_LABELS, timeAgo } from '../utils'
import { useLatestStates } from '../hooks/useData'

// ============================================================
// Confidence bar = 60% score component + 40% activity component
// Both normalized to 0-100 before combining
//
// Score component:   how far above threshold the signal is
// Activity component: how intense the raw market moves are
// ============================================================
function calcConfidence(score, m) {
  if (!m) return 0

  // Score component — normalize: score 0→0%, score 5+→100%
  const scoreNorm = Math.min(100, (score * 100) / 5)

  // Activity component — raw move intensity (same as before but normalized)
  const activity = Math.min(100,
    Math.abs(m.btc_chg    || 0) * 5  +
    Math.abs(m.btcd_chg   || 0) * 20 +
    Math.abs(m.total2_chg || 0) * 4
  )

  // Weighted combination
  return Math.round(scoreNorm * 0.6 + activity * 0.4)
}

function confidenceLabel(pct) {
  if (pct < 30) return 'Weak'
  if (pct < 60) return 'Moderate'
  if (pct < 85) return 'Strong'
  return 'Very Strong'
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

              {/* Score as multiplier */}
              {s && (
                <div className="state-score">
                  Χ{(score).toFixed(1)} above trigger {/* How many X did from the thredshold */}
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
                  {/* {s
                    ? `${confidence}% `
                    : 'No signal'
                  } */}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}