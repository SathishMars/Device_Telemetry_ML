import { useState, useEffect } from 'react'
import './App.css'
import Summary from './components/Summary'
import PS1Panel from './components/PS1Panel'
import PS2Panel from './components/PS2Panel'
import PS3Panel from './components/PS3Panel'
import PS4Panel from './components/PS4Panel'
import PS5Panel from './components/PS5Panel'
import LivePredictions from './components/LivePredictions'

const API_URL = 'http://localhost:8000'

const TABS = [
  { id: 'summary', label: 'Overview' },
  { id: 'live', label: 'Live Predictions' },
  { id: 'ps1', label: 'PS-1: Failure Prediction' },
  { id: 'ps2', label: 'PS-2: Error Patterns' },
  { id: 'ps3', label: 'PS-3: Root Cause' },
  { id: 'ps4', label: 'PS-4: Anomaly Detection' },
  { id: 'ps5', label: 'PS-5: SLA Risk' },
]

function App() {
  const [activeTab, setActiveTab] = useState('summary')
  const [data, setData] = useState(null)
  const [psData, setPsData] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchSummary()
  }, [])

  useEffect(() => {
    if (activeTab !== 'summary' && !psData[activeTab]) {
      fetchPsData(activeTab)
    }
  }, [activeTab])

  const fetchSummary = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_URL}/dashboard/summary`)
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      const json = await res.json()
      setData(json)
      setError(null)
    } catch (err) {
      setError(`Cannot connect to API at ${API_URL}. Make sure the API is running: python api/main.py`)
    } finally {
      setLoading(false)
    }
  }

  const fetchPsData = async (ps) => {
    try {
      const res = await fetch(`${API_URL}/dashboard/${ps}`)
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      const json = await res.json()
      setPsData(prev => ({ ...prev, [ps]: json }))
    } catch (err) {
      console.error(`Failed to fetch ${ps}:`, err)
    }
  }

  if (loading) {
    return (
      <div className="app">
        <div className="loading">Loading dashboard data...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="app">
        <header className="header">
          <h1>Device Telemetry ML Dashboard</h1>
          <span className="subtitle">London Metro Reader Monitoring</span>
        </header>
        <div className="error-box">
          <h3>Connection Error</h3>
          <p>{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Device Telemetry ML Dashboard</h1>
        <span className="subtitle">London Metro Reader Monitoring System</span>
        <div className="header-stats">
          <span className="stat">Models: {data?.api_status?.models_loaded?.length || 0}</span>
          <span className="stat">Predictions: {data?.api_status?.total_predictions || 0}</span>
          <span className="stat">Uptime: {Math.round((data?.api_status?.uptime_seconds || 0) / 60)}m</span>
        </div>
      </header>

      <nav className="tabs">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="content">
        {activeTab === 'summary' && <Summary data={data} />}
        {activeTab === 'live' && <LivePredictions />}
        {activeTab === 'ps1' && <PS1Panel data={data?.ps1_failure_prediction} detail={psData.ps1} />}
        {activeTab === 'ps2' && <PS2Panel data={data?.ps2_error_patterns} detail={psData.ps2} />}
        {activeTab === 'ps3' && <PS3Panel data={data?.ps3_root_cause} detail={psData.ps3} />}
        {activeTab === 'ps4' && <PS4Panel data={data?.ps4_anomaly_detection} detail={psData.ps4} />}
        {activeTab === 'ps5' && <PS5Panel data={data?.ps5_sla_risk} detail={psData.ps5} />}
      </main>
    </div>
  )
}

export default App
