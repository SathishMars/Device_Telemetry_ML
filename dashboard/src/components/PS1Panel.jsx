import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function PS1Panel({ data, detail }) {
  if (!data) return <div className="loading">Loading PS-1 data...</div>

  const metrics = detail?.champion_metrics || data

  return (
    <div>
      <div className="panel">
        <h2>PS-1: Failure Prediction</h2>
        <p className="desc">Predicts device failure in next 3 days using Random Forest, XGBoost, and CatBoost</p>

        <div className="cards">
          <div className="card">
            <h3>Champion Model</h3>
            <div className="value blue">{metrics.model || metrics.champion_model || 'N/A'}</div>
          </div>
          <div className="card">
            <h3>AUC-ROC</h3>
            <div className={`value ${(metrics.auc || 0) > 0.9 ? 'green' : 'yellow'}`}>
              {(metrics.auc || 0).toFixed(4)}
            </div>
          </div>
          <div className="card">
            <h3>F1 Score</h3>
            <div className="value blue">{(metrics.f1 || 0).toFixed(4)}</div>
          </div>
          <div className="card">
            <h3>Precision</h3>
            <div className="value green">{(metrics.precision || 0).toFixed(4)}</div>
          </div>
          <div className="card">
            <h3>Recall</h3>
            <div className="value yellow">{(metrics.recall || 0).toFixed(4)}</div>
          </div>
          <div className="card">
            <h3>Avg Precision</h3>
            <div className="value blue">{(metrics.avg_precision || metrics.accuracy || 0).toFixed(4)}</div>
          </div>
        </div>
      </div>

      {/* Model Comparison */}
      <div className="panel">
        <h2>Model Comparison</h2>
        <p className="desc">Champion vs Challenger models</p>
        {(() => {
          const models = detail?.models_compared || ['Random Forest', 'XGBoost', 'CatBoost']
          const chartData = [
            { name: 'AUC-ROC', value: (metrics.auc || 0) },
            { name: 'F1 Score', value: (metrics.f1 || 0) },
            { name: 'Precision', value: (metrics.precision || 0) },
            { name: 'Recall', value: (metrics.recall || 0) },
          ]
          return (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={chartData}>
                <XAxis dataKey="name" stroke="#64748b" />
                <YAxis domain={[0, 1]} stroke="#64748b" />
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
                <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )
        })()}
      </div>

      <div className="panel">
        <h2>Champion vs Challenger</h2>
        <table>
          <thead>
            <tr><th>Aspect</th><th>Champion</th><th>Challenger</th></tr>
          </thead>
          <tbody>
            <tr><td>Model</td><td><strong>{metrics.model || 'XGBoost'}</strong> (Production)</td><td>CatBoost / RF (Staging)</td></tr>
            <tr><td>Traffic</td><td>100%</td><td>0% (evaluation only)</td></tr>
            <tr><td>Stage</td><td><span className="badge low">Production</span></td><td><span className="badge medium">Staging</span></td></tr>
            <tr><td>Promotion</td><td>Current best AUC</td><td>Promoted if outperforms on next retrain</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
