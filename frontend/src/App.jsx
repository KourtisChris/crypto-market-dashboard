import { useEffect } from 'react'
import { useStore }  from './store'
import { fetchSnapshot } from './hooks/useData'
import { useWebSocket }  from './hooks/useWebSocket'

import Topbar       from './components/Topbar'
import AlertBanner  from './components/AlertBanner'
import StateCards   from './components/StateCards'
import MetricCards  from './components/MetricCards'
import Heatmap      from './components/Heatmap'
import TopMovers    from './components/TopMovers'
import StateHistory from './components/StateHistory'

export default function App() {
  const setSnapshot = useStore(s => s.setSnapshot)
  const prices      = useStore(s => s.prices)

  // Connect WebSocket
  useWebSocket()

  // Initial REST load
  useEffect(() => {
    fetchSnapshot()
      .then(setSnapshot)
      .catch(err => console.error('Initial load failed:', err))
  }, [])

  const isLoading = !prices.BTCUSDT

  return (
    <div className="app">
      <Topbar />
      {isLoading ? (
        <div className="loading-screen">
          <div className="spinner" />
          <div className="loading-text">Connecting to market data...</div>
        </div>
      ) : (
        <main className="container">
          <AlertBanner />
          <StateCards />
          <MetricCards />
          <Heatmap />
          <TopMovers />
          <StateHistory />
        </main>
      )}
    </div>
  )
}
