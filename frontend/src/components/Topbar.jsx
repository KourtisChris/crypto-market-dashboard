import { useState, useEffect } from 'react'
import { useStore } from '../store'

export default function Topbar() {
  const connected = useStore(s => s.connected)
  const [utc, setUtc]         = useState('')
  const [showModal, setModal] = useState(false)

  useEffect(() => {
    const tick = () => {
      const now  = new Date()
      const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      const tz   = Intl.DateTimeFormat().resolvedOptions().timeZone
      setUtc(`${time} ${tz}`)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <>
      <header className="topbar">
        <div className="topbar-left">
          <div className="logo">CRYPTO<span>.</span>STATE</div>
          <div className={`live-indicator ${connected ? 'live' : 'offline'}`}>
            <span className="live-dot" />
            {connected ? 'LIVE' : 'RECONNECTING'}
          </div>
        </div>
        <div className="topbar-right">
          <div className="utc-clock">{utc}</div>
          <button className="notif-btn" onClick={() => setModal(true)}>
            🔔 Alerts
          </button>
        </div>
      </header>

      {showModal && (
        <div className="modal-overlay" onClick={() => setModal(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setModal(false)}>✕</button>
            <div className="modal-title">📬 Get Market State Alerts</div>
            <div className="modal-body">
              <p>Receive instant Telegram notifications whenever the market state changes.</p>
              <div className="modal-steps">
                <div className="modal-step">
                  <span className="step-num">1</span>
                  <span>Open the Telegram bot:</span>
                </div>
                <a
                  href="https://t.me/TestMarketStateAlert_bot"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="modal-bot-link"
                >
                  @TestMarketStateAlert_bot
                </a>
                <div className="modal-step">
                  <span className="step-num">2</span>
                  <span>Press <code>/start</code> in the chat</span>
                </div>
                <div className="modal-step">
                  <span className="step-num">3</span>
                  <span>Done! You will receive alerts for every state change.</span>
                </div>
              </div>
              <p className="modal-note">Send <code>/stop</code> to the bot to unsubscribe at any time.</p>
            </div>
          </div>
        </div>
      )}
    </>
  )
}