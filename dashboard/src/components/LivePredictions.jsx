import { useState } from 'react'

const API_URL = 'http://localhost:8000'

const SAMPLE_DEVICES = [
  {device_id:"LMR_0001",signal_strength_dbm:45,temperature_c:52,response_time_ms:350,network_latency_ms:55,power_voltage:3.8,memory_usage_pct:85,cpu_usage_pct:78,error_count:8,reboot_count:2,uptime_hours:18.5,daily_taps:400,tap_success_rate:0.78,health_score:35,age_days:1200,cumulative_errors:150,cumulative_reboots:25,total_maintenance_count:12,corrective_count:8,emergency_count:3},
  {device_id:"LMR_0002",signal_strength_dbm:92,temperature_c:30,response_time_ms:80,network_latency_ms:12,power_voltage:5.1,memory_usage_pct:35,cpu_usage_pct:22,error_count:0,reboot_count:0,uptime_hours:24,daily_taps:1200,tap_success_rate:0.99,health_score:95,age_days:180,cumulative_errors:3,cumulative_reboots:1,total_maintenance_count:1,corrective_count:0,emergency_count:0},
  {device_id:"LMR_0003",signal_strength_dbm:55,temperature_c:48,response_time_ms:280,network_latency_ms:45,power_voltage:4.2,memory_usage_pct:72,cpu_usage_pct:65,error_count:5,reboot_count:1,uptime_hours:20,daily_taps:600,tap_success_rate:0.82,health_score:42,age_days:900,cumulative_errors:95,cumulative_reboots:15,total_maintenance_count:8,corrective_count:5,emergency_count:2},
  {device_id:"LMR_0004",signal_strength_dbm:88,temperature_c:33,response_time_ms:95,network_latency_ms:14,power_voltage:5.0,memory_usage_pct:40,cpu_usage_pct:28,error_count:1,reboot_count:0,uptime_hours:23.5,daily_taps:1100,tap_success_rate:0.97,health_score:88,age_days:365,cumulative_errors:12,cumulative_reboots:2,total_maintenance_count:2,corrective_count:1,emergency_count:0},
  {device_id:"LMR_0005",signal_strength_dbm:38,temperature_c:58,response_time_ms:450,network_latency_ms:70,power_voltage:3.5,memory_usage_pct:92,cpu_usage_pct:88,error_count:12,reboot_count:4,uptime_hours:15,daily_taps:200,tap_success_rate:0.65,health_score:18,age_days:1500,cumulative_errors:220,cumulative_reboots:40,total_maintenance_count:18,corrective_count:12,emergency_count:5},
]

const TIER_COLORS = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#eab308',
  LOW: '#22c55e',
  ANOMALY: '#ef4444',
  NORMAL: '#22c55e',
}

export default function LivePredictions() {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [customJson, setCustomJson] = useState('')
  const [selectedDevice, setSelectedDevice] = useState(null)

  const runPredictions = async (devices) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_URL}/predict/batch/all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ devices })
      })
      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || `API returned ${res.status}`)
      }
      const data = await res.json()
      setResults(data)
      setSelectedDevice(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const runSamplePredictions = () => runPredictions(SAMPLE_DEVICES)

  const runCustomPredictions = () => {
    try {
      const parsed = JSON.parse(customJson)
      const devices = Array.isArray(parsed) ? parsed : parsed.devices || [parsed]
      runPredictions(devices)
    } catch {
      setError('Invalid JSON. Paste a device object or array of device objects.')
    }
  }

  const getTierBadge = (tier) => (
    <span style={{
      background: TIER_COLORS[tier] || '#6b7280',
      color: '#fff',
      padding: '2px 10px',
      borderRadius: '12px',
      fontSize: '11px',
      fontWeight: 700
    }}>{tier}</span>
  )

  return (
    <div className="panel">
      <h2>Live Predictions — All 5 Problem Statements</h2>
      <p style={{color:'#94a3b8', marginBottom:'16px'}}>
        Send device telemetry and get predictions from PS-1 (Failure), PS-2 (Error Patterns),
        PS-3 (Root Cause), PS-4 (Anomaly), and PS-5 (SLA Risk) in one call.
      </p>

      <div style={{display:'flex', gap:'12px', marginBottom:'20px'}}>
        <button
          onClick={runSamplePredictions}
          disabled={loading}
          style={{
            background:'#3b82f6', color:'#fff', border:'none', padding:'10px 24px',
            borderRadius:'8px', cursor:'pointer', fontWeight:600, fontSize:'14px'
          }}
        >
          {loading ? 'Running...' : 'Run Sample (5 Devices)'}
        </button>
      </div>

      <details style={{marginBottom:'20px'}}>
        <summary style={{cursor:'pointer', color:'#60a5fa', fontSize:'13px'}}>
          Or paste custom device JSON
        </summary>
        <textarea
          value={customJson}
          onChange={(e) => setCustomJson(e.target.value)}
          placeholder='[{"device_id":"LMR_0099","signal_strength_dbm":50,...}]'
          style={{
            width:'100%', height:'120px', marginTop:'8px', background:'#1e293b',
            border:'1px solid #334155', borderRadius:'8px', color:'#e2e8f0',
            padding:'10px', fontFamily:'monospace', fontSize:'12px'
          }}
        />
        <button
          onClick={runCustomPredictions}
          disabled={loading}
          style={{
            background:'#8b5cf6', color:'#fff', border:'none', padding:'8px 20px',
            borderRadius:'8px', cursor:'pointer', fontWeight:600, marginTop:'8px'
          }}
        >
          Run Custom Predictions
        </button>
      </details>

      {error && (
        <div style={{background:'#7f1d1d', padding:'12px', borderRadius:'8px', marginBottom:'16px'}}>
          {error}
        </div>
      )}

      {results && (
        <>
          {/* Fleet Summary Cards */}
          <div style={{display:'grid', gridTemplateColumns:'repeat(5, 1fr)', gap:'12px', marginBottom:'24px'}}>
            <div className="kpi-card">
              <div className="kpi-label">PS-1: Failure Risk</div>
              <div className="kpi-value" style={{color:'#f87171'}}>
                {results.summary?.ps1_summary?.critical || 0} CRIT
              </div>
              <div style={{fontSize:'12px',color:'#94a3b8'}}>
                {results.summary?.ps1_summary?.high || 0} HIGH |
                {results.summary?.ps1_summary?.medium || 0} MED |
                {results.summary?.ps1_summary?.low || 0} LOW
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">PS-2: Error Patterns</div>
              <div className="kpi-value" style={{color:'#f472b6'}}>
                {results.summary?.ps2_summary?.devices_with_errors || 0}
              </div>
              <div style={{fontSize:'12px',color:'#94a3b8'}}>
                devices with errors
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">PS-3: Risk Factors</div>
              <div className="kpi-value" style={{color:'#fb923c'}}>
                {results.summary?.ps3_summary?.devices_with_risk_factors || 0}
              </div>
              <div style={{fontSize:'12px',color:'#94a3b8'}}>
                {results.summary?.ps3_summary?.top_cause_across_fleet?.cause || 'N/A'}
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">PS-4: Anomalies</div>
              <div className="kpi-value" style={{color:'#ef4444'}}>
                {results.summary?.ps4_summary?.anomalies || 0}
              </div>
              <div style={{fontSize:'12px',color:'#94a3b8'}}>
                of {results.summary?.total_devices || 0} devices
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">PS-5: SLA Risk</div>
              <div className="kpi-value" style={{color:'#2dd4bf'}}>
                {results.summary?.ps5_summary?.avg_rul_days || 0}d
              </div>
              <div style={{fontSize:'12px',color:'#94a3b8'}}>
                avg RUL | {results.summary?.ps5_summary?.critical || 0} CRIT
              </div>
            </div>
          </div>

          {/* Per-Device Results Table */}
          <h3 style={{marginBottom:'12px'}}>Per-Device Results ({results.devices?.length} devices)</h3>
          <div style={{overflowX:'auto'}}>
            <table className="data-table" style={{width:'100%'}}>
              <thead>
                <tr>
                  <th>Device</th>
                  <th>PS-1: Failure</th>
                  <th>PS-2: Errors</th>
                  <th>PS-3: Root Cause</th>
                  <th>PS-4: Anomaly</th>
                  <th>PS-5: SLA Risk</th>
                </tr>
              </thead>
              <tbody>
                {results.devices?.map((d, i) => (
                  <tr
                    key={i}
                    onClick={() => setSelectedDevice(d)}
                    style={{cursor:'pointer', background: selectedDevice?.device_id === d.device_id ? '#1e3a5f' : 'transparent'}}
                  >
                    <td style={{fontWeight:700, color:'#60a5fa'}}>{d.device_id}</td>
                    <td>
                      {d.ps1_failure?.failure_probability != null
                        ? <>{(d.ps1_failure.failure_probability * 100).toFixed(1)}% {getTierBadge(d.ps1_failure.risk_tier)}</>
                        : <span style={{color:'#6b7280'}}>N/A</span>}
                    </td>
                    <td>
                      {getTierBadge(d.ps2_error_patterns?.error_severity || 'LOW')}
                      <span style={{marginLeft:'6px', fontSize:'12px'}}>
                        {d.ps2_error_patterns?.error_count || 0} errors
                      </span>
                    </td>
                    <td style={{fontSize:'12px'}}>
                      {d.ps3_root_cause?.primary_cause || 'None'}
                      {d.ps3_root_cause?.total_risk_factors > 0 &&
                        <span style={{color:'#f97316'}}> ({d.ps3_root_cause.total_risk_factors})</span>}
                    </td>
                    <td>
                      {d.ps4_anomaly?.is_anomaly != null
                        ? getTierBadge(d.ps4_anomaly.is_anomaly ? 'ANOMALY' : 'NORMAL')
                        : <span style={{color:'#6b7280'}}>N/A</span>}
                    </td>
                    <td>
                      {d.ps5_sla_risk?.risk_tier
                        ? <>{d.ps5_sla_risk.rul_estimate_days}d {getTierBadge(d.ps5_sla_risk.risk_tier)}</>
                        : <span style={{color:'#6b7280'}}>N/A</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Selected Device Detail */}
          {selectedDevice && (
            <div style={{marginTop:'24px', background:'#0f172a', padding:'20px', borderRadius:'12px', border:'1px solid #1e293b'}}>
              <h3 style={{color:'#60a5fa', marginBottom:'16px'}}>
                Device Detail: {selectedDevice.device_id}
              </h3>

              <div style={{display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:'16px'}}>
                {/* PS-1 Detail */}
                <div>
                  <h4 style={{color:'#f87171', marginBottom:'8px'}}>PS-1: Failure Prediction</h4>
                  {selectedDevice.ps1_failure && !selectedDevice.ps1_failure.error ? (
                    <>
                      <p>Probability: <strong>{(selectedDevice.ps1_failure.failure_probability * 100).toFixed(2)}%</strong></p>
                      <p>Risk: {getTierBadge(selectedDevice.ps1_failure.risk_tier)}</p>
                      <p>Confidence: {selectedDevice.ps1_failure.confidence}</p>
                      <p style={{fontSize:'12px', color:'#94a3b8', marginTop:'4px'}}>
                        {selectedDevice.ps1_failure.recommended_action}
                      </p>
                    </>
                  ) : <p style={{color:'#6b7280'}}>Model not loaded</p>}
                </div>

                {/* PS-2 Detail */}
                <div>
                  <h4 style={{color:'#f472b6', marginBottom:'8px'}}>PS-2: Error Patterns</h4>
                  <p>Errors today: <strong>{selectedDevice.ps2_error_patterns?.error_count}</strong></p>
                  <p>Severity: {getTierBadge(selectedDevice.ps2_error_patterns?.error_severity)}</p>
                  <p>Error rate/day: {selectedDevice.ps2_error_patterns?.error_rate_per_day}</p>
                  <p>Reboot freq/mo: {selectedDevice.ps2_error_patterns?.reboot_frequency}</p>
                  <p>Likely escalation: {selectedDevice.ps2_error_patterns?.likely_escalation ? 'YES' : 'No'}</p>
                </div>

                {/* PS-3 Detail */}
                <div>
                  <h4 style={{color:'#fb923c', marginBottom:'8px'}}>PS-3: Root Cause</h4>
                  <p>Primary: <strong>{selectedDevice.ps3_root_cause?.primary_cause}</strong></p>
                  <p>Risk factors: {selectedDevice.ps3_root_cause?.total_risk_factors}</p>
                  {selectedDevice.ps3_root_cause?.risk_factors?.slice(0, 4).map((f, i) => (
                    <p key={i} style={{fontSize:'12px'}}>
                      {getTierBadge(f.impact)} {f.factor}: {f.value}
                    </p>
                  ))}
                </div>

                {/* PS-4 Detail */}
                <div>
                  <h4 style={{color:'#ef4444', marginBottom:'8px'}}>PS-4: Anomaly Detection</h4>
                  {selectedDevice.ps4_anomaly && !selectedDevice.ps4_anomaly.error ? (
                    <>
                      <p>Status: {getTierBadge(selectedDevice.ps4_anomaly.is_anomaly ? 'ANOMALY' : 'NORMAL')}</p>
                      <p>Score: <strong>{selectedDevice.ps4_anomaly.anomaly_score?.toFixed(4)}</strong></p>
                      {selectedDevice.ps4_anomaly.is_anomaly && selectedDevice.ps4_anomaly.anomaly_features &&
                        Object.entries(selectedDevice.ps4_anomaly.anomaly_features).slice(0, 4).map(([k, v]) => (
                          <p key={k} style={{fontSize:'12px'}}>{k}: {v}</p>
                        ))
                      }
                    </>
                  ) : <p style={{color:'#6b7280'}}>Model not loaded</p>}
                </div>

                {/* PS-5 Detail */}
                <div>
                  <h4 style={{color:'#2dd4bf', marginBottom:'8px'}}>PS-5: SLA Risk</h4>
                  {selectedDevice.ps5_sla_risk && !selectedDevice.ps5_sla_risk.error ? (
                    <>
                      <p>SLA Score: <strong>{selectedDevice.ps5_sla_risk.sla_risk_score}</strong>/100</p>
                      <p>Risk: {getTierBadge(selectedDevice.ps5_sla_risk.risk_tier)}</p>
                      <p>RUL: <strong>{selectedDevice.ps5_sla_risk.rul_estimate_days} days</strong></p>
                      <p style={{fontSize:'12px', color:'#94a3b8', marginTop:'4px'}}>
                        {selectedDevice.ps5_sla_risk.recommended_action}
                      </p>
                    </>
                  ) : <p style={{color:'#6b7280'}}>RUL data not loaded</p>}
                </div>
              </div>

              <div style={{marginTop:'16px', fontSize:'11px', color:'#475569'}}>
                Processing time: {results.summary?.processing_time_ms?.toFixed(1)}ms
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
