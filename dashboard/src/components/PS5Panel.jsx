import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'

const RISK_COLORS = { CRITICAL: '#ef4444', HIGH: '#f59e0b', MEDIUM: '#eab308', LOW: '#22c55e' }

export default function PS5Panel({ data, detail }) {
  if (!data) return <div className="loading">Loading PS-5 data...</div>

  const rulEstimates = detail?.rul_estimates || data.rul_estimates || []
  const slaScores = detail?.sla_risk_scores || data.sla_risk_scores || []
  const coxSummary = detail?.cox_summary || []
  const riskDist = data.risk_distribution || {}

  const pieData = Object.entries(riskDist).map(([name, value]) => ({ name, value }))
  const pieColors = pieData.map(d => RISK_COLORS[d.name] || '#64748b')

  const rulHist = [
    { range: '0-7d', count: rulEstimates.filter(r => (r.rul_median_days || 0) <= 7).length },
    { range: '8-14d', count: rulEstimates.filter(r => (r.rul_median_days || 0) > 7 && (r.rul_median_days || 0) <= 14).length },
    { range: '15-30d', count: rulEstimates.filter(r => (r.rul_median_days || 0) > 14 && (r.rul_median_days || 0) <= 30).length },
    { range: '31-60d', count: rulEstimates.filter(r => (r.rul_median_days || 0) > 30 && (r.rul_median_days || 0) <= 60).length },
    { range: '60+d', count: rulEstimates.filter(r => (r.rul_median_days || 0) > 60).length },
  ]

  return (
    <div>
      <div className="panel">
        <h2>PS-5: SLA Risk Prediction</h2>
        <p className="desc">Estimates Remaining Useful Life and SLA breach risk using Weibull, Cox Proportional Hazards</p>

        <div className="cards">
          <div className="card">
            <h3>Mean RUL</h3>
            <div className="value blue">{data.mean_rul_days || 0} days</div>
            <div className="sub">Average remaining useful life</div>
          </div>
          <div className="card">
            <h3>Critical Devices</h3>
            <div className="value red">{riskDist.CRITICAL || 0}</div>
            <div className="sub">Need immediate attention</div>
          </div>
          <div className="card">
            <h3>High Risk</h3>
            <div className="value yellow">{riskDist.HIGH || 0}</div>
            <div className="sub">Schedule maintenance within 48h</div>
          </div>
          <div className="card">
            <h3>Healthy Devices</h3>
            <div className="value green">{(riskDist.LOW || 0) + (riskDist.MEDIUM || 0)}</div>
            <div className="sub">Standard monitoring sufficient</div>
          </div>
        </div>
      </div>

      <div className="grid-2">
        {/* Risk Distribution Pie */}
        <div className="panel">
          <h2>Risk Tier Distribution</h2>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100}
                  label={({ name, value }) => `${name}: ${value}`}>
                  {pieData.map((_, i) => <Cell key={i} fill={pieColors[i]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : <p className="sub">No data</p>}
        </div>

        {/* RUL Histogram */}
        <div className="panel">
          <h2>RUL Distribution</h2>
          <p className="desc">Remaining Useful Life distribution across devices</p>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={rulHist}>
              <XAxis dataKey="range" stroke="#64748b" />
              <YAxis stroke="#64748b" />
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
              <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Devices" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* RUL Estimates Table */}
      <div className="panel">
        <h2>Device RUL Estimates</h2>
        <p className="desc">Per-device remaining useful life and risk assessment</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Device ID</th><th>RUL (days)</th><th>Survival Prob</th><th>Health Score</th><th>Risk Tier</th></tr>
            </thead>
            <tbody>
              {rulEstimates.slice(0, 20).map((r, i) => (
                <tr key={i}>
                  <td><strong>{r.device_id}</strong></td>
                  <td>{r.rul_median_days}</td>
                  <td>{(r.current_survival_prob || 0).toFixed(4)}</td>
                  <td>{(r.health_score || 0).toFixed(1)}</td>
                  <td><span className={`badge ${(r.risk_tier || '').toLowerCase()}`}>{r.risk_tier}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Cox PH Summary */}
      {coxSummary.length > 0 && (
        <div className="panel">
          <h2>Cox Proportional Hazards — Covariate Effects</h2>
          <p className="desc">How each factor affects failure risk (hazard ratio)</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Covariate</th><th>Coefficient</th><th>Hazard Ratio</th><th>p-value</th><th>Significant</th></tr>
              </thead>
              <tbody>
                {coxSummary.map((c, i) => {
                  const hr = Math.exp(c.coef || 0)
                  return (
                    <tr key={i}>
                      <td>{(c.covariate || c.Unnamed || `Var ${i}`).replace(/_/g, ' ')}</td>
                      <td>{(c.coef || 0).toFixed(4)}</td>
                      <td style={{ color: hr > 1 ? '#f87171' : '#4ade80' }}>
                        <strong>{hr.toFixed(3)}</strong> {hr > 1 ? '(increases risk)' : '(decreases risk)'}
                      </td>
                      <td>{(c.p || 0).toFixed(4)}</td>
                      <td>{(c.p || 1) < 0.05 ? <span className="badge critical">Yes</span> : <span className="badge low">No</span>}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SLA Risk Scores */}
      {slaScores.length > 0 && (
        <div className="panel">
          <h2>Top SLA Risk Devices</h2>
          <p className="desc">Devices most likely to breach SLA targets</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Device ID</th><th>SLA Risk Score</th><th>SLA Breach Prob</th><th>Health Score</th><th>Cumulative Errors</th></tr>
              </thead>
              <tbody>
                {slaScores.slice(0, 10).map((s, i) => (
                  <tr key={i}>
                    <td><strong>{s.device_id}</strong></td>
                    <td style={{ color: (s.sla_risk_score || 0) > 60 ? '#f87171' : '#4ade80' }}>
                      <strong>{(s.sla_risk_score || 0).toFixed(1)}</strong>
                    </td>
                    <td>{(s.sla_breach_prob || 0).toFixed(4)}</td>
                    <td>{(s.health_score || 0).toFixed(1)}</td>
                    <td>{s.cumulative_errors || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
