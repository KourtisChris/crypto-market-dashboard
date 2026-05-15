import { useStore } from '../store'
import { typeClass, timeAgo, TF_LABELS } from '../utils'

export default function AlertBanner() {
  const lastAlert = useStore(s => s.lastAlert)
  const states    = useStore(s => s.states)

  const alert = lastAlert && (Date.now() - lastAlert.receivedAt < 300_000)
    ? lastAlert
    : (() => {
        const s = states['1H']
        return s ? { state_label: s.label, state_type: s.type, tf: '1H', receivedAt: null } : null
      })()

  if (!alert) return null

  return (
    <div className="last-change-section">
      <div className="section-title">Last State Change</div>
      <div className={`alert-banner ${typeClass(alert.state_type)}`}>
        <div className="banner-tf">{TF_LABELS[alert.tf] || alert.tf}</div>
        <div className="banner-label">{alert.state_label}</div>
        {alert.receivedAt && (
          <>
            <div className="banner-tag">NEW</div>
            <div className="banner-time">{timeAgo(alert.receivedAt)}</div>
          </>
        )}
      </div>
    </div>
  )
}
