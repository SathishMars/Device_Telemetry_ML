import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'

const COLORS = ['#ef4444', '#f59e0b', '#eab308', '#22c55e']

export default function Summary({ data }) {
  if (!data) return null

  const ps1 = data.ps1_failure_prediction || {}
  const ps4 = data.ps4_anomaly_detection || {}
  const ps5 = data.ps5_sla_risk || {}
  const drift = data.drift_detection || {}
  const quality = data.data_quality || {}

  const riskDist = ps5.risk_distribution || {}
  const pieData = Object.entries(riskDist).map(([name, value]) => ({ name, value }))

  const spcData = (ps4.spc_results || []).map(r => ({
    name: (r.feature || '').replace(/_/g, ' ').slice(0, 15),
    violations: r.violations || 0,
    warnings: r.warnings || 0,
  }))

  return (
    <div>
      {/* KPI Cards */}
      <div className="cards">
        <div className="card">
          <h3>PS-1: Champion Model</h3>
          <div className="value blue">{ps1.champion_model || 'N/A'}</div>
          <div className="sub">AUC: {(ps1.auc || 0).toFixed(4)} | F1: {(ps1.f1 || 0).toFixed(4)}</div>
        </div>
        <div className="card">
          <h3>PS-2: Association Rules</h3>
          <div className="value green">{data.ps2_error_patterns?.association_rules || 0}</div>
          <div className="sub">Error co-occurrence patterns found</div>
        </div>
        <div className="card">
          <h3>PS-3: Top Root Cause</h3>
          <div className="value yellow">
            {(data.ps3_root_cause?.shap_importance?.[0]?.feature || 'N/A').replace(/_/g, ' ')}
          </div>
          <div className="sub">SHAP: {(data.ps3_root_cause?.shap_importance?.[0]?.mean_abs_shap || 0).toFixed(4)}</div>
        </div>
        <div className="card">
          <h3>PS-4: Anomalies Detected</h3>
          <div className="value red">{ps4.anomaly_summary?.length || 0} devices</div>
          <div className="sub">SPC Violations: {spcData.reduce((s, d) => s + d.violations, 0)}</div>
        </div>
        <div className="card">
          <h3>PS-5: Mean RUL</h3>
          <div className="value blue">{ps5.mean_rul_days || 0} days</div>
          <div className="sub">Average remaining useful life</div>
        </div>
        <div className="card">
          <h3>Drift Status</h3>
          <div className={`value ${drift.should_retrain ? 'red' : 'green'}`}>
            {drift.should_retrain ? 'RETRAIN NEEDED' : 'STABLE'}
          </div>
          <div className="sub">Drift share: {((drift.drift_share || 0) * 100).toFixed(1)}%</div>
        </div>
        <div className="card">
          <h3>Data Quality</h3>
          <div className="value green">{quality.overall_pass_rate?.toFixed(0) || 0}%</div>
          <div className="sub">{quality.passed || 0}/{quality.total_expectations || 0} checks passed</div>
        </div>
      </div>

      <div className="grid-2">
        {/* Risk Distribution Pie */}
        <div className="panel">
          <h2>PS-5: Device Risk Distribution</h2>
          <p className="desc">RUL-based risk tiers across all devices</p>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={({ name, value }) => `${name}: ${value}`}>
                  {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : <p className="sub">No data available</p>}
        </div>

        {/* SPC Violations */}
        <div className="panel">
          <h2>PS-4: SPC Control Chart Violations</h2>
          <p className="desc">3-sigma violations by telemetry feature</p>
          {spcData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={spcData} layout="vertical">
                <XAxis type="number" stroke="#64748b" />
                <YAxis dataKey="name" type="category" width={120} stroke="#64748b" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
                <Bar dataKey="violations" fill="#ef4444" name="Violations" />
                <Bar dataKey="warnings" fill="#f59e0b" name="Warnings" />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="sub">No data available</p>}
        </div>
      </div>
    </div>
  )
}
