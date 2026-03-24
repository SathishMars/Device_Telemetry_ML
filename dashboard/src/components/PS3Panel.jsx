import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function PS3Panel({ data, detail }) {
  if (!data) return <div className="loading">Loading PS-3 data...</div>

  const shapImportance = detail?.shap_importance || data.shap_importance || []
  const causalResults = detail?.causal_results || data.causal_results || []
  const localExplanation = detail?.local_explanation || []

  const shapChart = shapImportance.slice(0, 15).map(s => ({
    name: (s.feature || '').replace(/_/g, ' ').slice(0, 20),
    value: s.mean_abs_shap || 0,
  })).reverse()

  return (
    <div>
      <div className="panel">
        <h2>PS-3: Root Cause Analysis</h2>
        <p className="desc">Identifies root causes of device failures using SHAP values and Causal Inference</p>

        <div className="cards">
          <div className="card">
            <h3>Top Root Cause</h3>
            <div className="value yellow">{(shapImportance[0]?.feature || 'N/A').replace(/_/g, ' ')}</div>
            <div className="sub">Mean |SHAP|: {(shapImportance[0]?.mean_abs_shap || 0).toFixed(4)}</div>
          </div>
          <div className="card">
            <h3>Features Analyzed</h3>
            <div className="value blue">{shapImportance.length}</div>
          </div>
          <div className="card">
            <h3>Causal Hypotheses Tested</h3>
            <div className="value green">{causalResults.length}</div>
          </div>
        </div>
      </div>

      {/* SHAP Feature Importance */}
      <div className="panel">
        <h2>SHAP Feature Importance (Global)</h2>
        <p className="desc">Mean |SHAP| value — higher means more impact on failure prediction</p>
        {shapChart.length > 0 ? (
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={shapChart} layout="vertical">
              <XAxis type="number" stroke="#64748b" />
              <YAxis dataKey="name" type="category" width={160} stroke="#64748b" tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
              <Bar dataKey="value" fill="#f59e0b" radius={[0, 4, 4, 0]} name="Mean |SHAP|" />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          shapImportance.slice(0, 10).map((s, i) => (
            <div className="bar-row" key={i}>
              <span className="bar-label">{(s.feature || '').replace(/_/g, ' ')}</span>
              <div className="bar-track">
                <div className="bar-fill orange" style={{ width: `${Math.min((s.mean_abs_shap / (shapImportance[0]?.mean_abs_shap || 1)) * 100, 100)}%` }}>
                  {(s.mean_abs_shap || 0).toFixed(4)}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="grid-2">
        {/* Causal Analysis */}
        <div className="panel">
          <h2>Causal Inference Results</h2>
          <p className="desc">Estimated causal effect of each factor on failure rate</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Treatment</th><th>Failure Rate (High)</th><th>Failure Rate (Low)</th><th>Difference</th><th>Risk Ratio</th></tr>
              </thead>
              <tbody>
                {causalResults.map((c, i) => (
                  <tr key={i}>
                    <td>{(c.treatment || '').replace(/_/g, ' ')}</td>
                    <td>{(c.failure_rate_high ?? c.ate ?? 0).toFixed(4)}</td>
                    <td>{(c.failure_rate_low ?? 0).toFixed(4)}</td>
                    <td style={{ color: (c.difference || c.ate || 0) > 0 ? '#f87171' : '#4ade80' }}>
                      <strong>{(c.difference || c.ate || 0) > 0 ? '+' : ''}{(c.difference || c.ate || 0).toFixed(4)}</strong>
                    </td>
                    <td>{(c.risk_ratio || 0).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Local Explanation */}
        <div className="panel">
          <h2>Local Explanation (Sample Device)</h2>
          <p className="desc">SHAP breakdown for a single prediction</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Feature</th><th>Value</th><th>SHAP Impact</th><th>Direction</th></tr>
              </thead>
              <tbody>
                {localExplanation.slice(0, 10).map((l, i) => (
                  <tr key={i}>
                    <td>{(l.feature || '').replace(/_/g, ' ')}</td>
                    <td>{(l.feature_value || 0).toFixed(2)}</td>
                    <td>{(l.shap_value || 0).toFixed(4)}</td>
                    <td style={{ color: (l.shap_value || 0) > 0 ? '#f87171' : '#4ade80' }}>
                      {(l.shap_value || 0) > 0 ? 'Increases failure risk' : 'Decreases failure risk'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
