import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function PS4Panel({ data, detail }) {
  if (!data) return <div className="loading">Loading PS-4 data...</div>

  const anomalySummary = detail?.device_anomaly_summary || data.anomaly_summary || []
  const spcResults = detail?.spc_results || data.spc_results || []
  const spcLimits = detail?.spc_limits || {}
  const featureDiff = detail?.feature_diff || data.feature_diff || []

  const diffChart = featureDiff.slice(0, 10).map(f => ({
    name: (f.feature || '').replace(/_/g, ' ').slice(0, 18),
    pct_diff: parseFloat(f.pct_diff) || 0,
  }))

  return (
    <div>
      <div className="panel">
        <h2>PS-4: Anomaly Detection</h2>
        <p className="desc">Detects abnormal device behavior using Isolation Forest and Statistical Process Control</p>

        <div className="cards">
          <div className="card">
            <h3>Anomalous Devices</h3>
            <div className="value red">{anomalySummary.length}</div>
            <div className="sub">Devices with detected anomalies</div>
          </div>
          <div className="card">
            <h3>SPC Violations</h3>
            <div className="value yellow">{spcResults.reduce((s, r) => s + (r.violations || 0), 0)}</div>
            <div className="sub">3-sigma control limit breaches</div>
          </div>
          <div className="card">
            <h3>SPC Warnings</h3>
            <div className="value blue">{spcResults.reduce((s, r) => s + (r.warnings || 0), 0)}</div>
            <div className="sub">2-sigma warning zone entries</div>
          </div>
        </div>
      </div>

      <div className="grid-2">
        {/* Feature Difference Chart */}
        <div className="panel">
          <h2>Anomaly vs Normal: Feature Differences</h2>
          <p className="desc">% difference in feature means between anomalous and normal readings</p>
          {diffChart.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={diffChart} layout="vertical">
                <XAxis type="number" stroke="#64748b" />
                <YAxis dataKey="name" type="category" width={140} stroke="#64748b" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} formatter={(v) => `${v.toFixed(1)}%`} />
                <Bar dataKey="pct_diff" fill="#ef4444" radius={[0, 4, 4, 0]} name="% Difference" />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="sub">No data</p>}
        </div>

        {/* SPC Control Limits */}
        <div className="panel">
          <h2>SPC Control Limits</h2>
          <p className="desc">Statistical Process Control parameters per feature</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Feature</th><th>Center Line</th><th>UCL (3σ)</th><th>LCL (3σ)</th><th>Violations</th><th>Warnings</th></tr>
              </thead>
              <tbody>
                {spcResults.map((r, i) => (
                  <tr key={i}>
                    <td>{(r.feature || '').replace(/_/g, ' ')}</td>
                    <td>{(r.center_line || 0).toFixed(2)}</td>
                    <td>{(r.ucl || 0).toFixed(2)}</td>
                    <td>{(r.lcl || 0).toFixed(2)}</td>
                    <td style={{ color: (r.violations || 0) > 0 ? '#f87171' : '#4ade80' }}>
                      <strong>{r.violations || 0}</strong>
                    </td>
                    <td style={{ color: (r.warnings || 0) > 0 ? '#fbbf24' : '#4ade80' }}>
                      {r.warnings || 0}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Top Anomalous Devices */}
      <div className="panel">
        <h2>Top Anomalous Devices</h2>
        <p className="desc">Devices ranked by number of anomalous days (Isolation Forest)</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Device ID</th><th>Anomaly Days</th><th>Total Days</th><th>Anomaly Rate</th><th>Status</th></tr>
            </thead>
            <tbody>
              {anomalySummary.slice(0, 15).map((d, i) => {
                const rate = d.anomaly_rate || (d.anomaly_count / d.total_days) || 0
                return (
                  <tr key={i}>
                    <td><strong>{d.device_id}</strong></td>
                    <td>{d.anomaly_count || d.sum || 0}</td>
                    <td>{d.total_days || d.count || 30}</td>
                    <td>{(rate * 100).toFixed(0)}%</td>
                    <td>
                      <span className={`badge ${rate > 0.3 ? 'critical' : rate > 0.15 ? 'high' : rate > 0.05 ? 'medium' : 'low'}`}>
                        {rate > 0.3 ? 'CRITICAL' : rate > 0.15 ? 'HIGH' : rate > 0.05 ? 'MEDIUM' : 'LOW'}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
