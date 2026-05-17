import { useStore } from '../store'
import { typeClass, timeAgo, TF_LABELS } from '../utils'
import { useLatestStates } from '../hooks/useData'

export default function AlertBanner() {
  const lastAlert    = useStore(s => s.lastAlert)
  const latestStates = useLatestStates()

  // Βρες το πιο πρόσφατο state change από τη βάση
  const mostRecent = Object.entries(latestStates)
    .filter(([, v]) => v?.recorded_at)
    .sort((a, b) => new Date(b[1].recorded_at) - new Date(a[1].recorded_at))[0]

  const alert = lastAlert && (Date.now() - lastAlert.receivedAt < 300_000)
    ? lastAlert
    : mostRecent
      ? { state_label: mostRecent[1].label, state_type: mostRecent[1].type, tf: mostRecent[0], receivedAt: null }
      : null

  if (!alert) return null

  return (
    <div className="last-change-section">
      <div className="section-title">Last State Change</div>
      <div className={`alert-banner ${typeClass(alert.state_type)}`}>
        <div className="banner-tf">{TF_LABELS[alert.tf] || alert.tf}</div>
        <div className="banner-label">{alert.state_label}</div>
        {alert.receivedAt
          ? <>
              <div className="banner-tag">NEW</div>
              <div className="banner-time">{timeAgo(alert.receivedAt)}</div>
            </>
          : mostRecent && (
              <div className="banner-time">{timeAgo(mostRecent[1].recorded_at)}</div>
            )
        }
      </div>
    </div>
  )
}