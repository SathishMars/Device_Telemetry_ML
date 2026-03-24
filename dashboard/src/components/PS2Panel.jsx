export default function PS2Panel({ data, detail }) {
  if (!data) return <div className="loading">Loading PS-2 data...</div>

  const rules = detail?.association_rules || []
  const transitions = data.top_transitions || detail?.top_transitions || []
  const escalations = data.severity_escalations || detail?.severity_escalations || []
  const stationary = detail?.stationary_distribution || []

  return (
    <div>
      <div className="panel">
        <h2>PS-2: Error Pattern Recognition</h2>
        <p className="desc">Discovers co-occurring errors (Apriori) and error sequences (Markov Chain)</p>

        <div className="cards">
          <div className="card">
            <h3>Association Rules Found</h3>
            <div className="value green">{data.association_rules || rules.length}</div>
          </div>
          <div className="card">
            <h3>Top Transitions</h3>
            <div className="value blue">{transitions.length}</div>
            <div className="sub">Significant error sequences</div>
          </div>
          <div className="card">
            <h3>Severity Escalations</h3>
            <div className="value red">{escalations.length}</div>
            <div className="sub">Escalation patterns detected</div>
          </div>
        </div>
      </div>

      {/* Association Rules */}
      <div className="panel">
        <h2>Association Rules (Apriori)</h2>
        <p className="desc">Error codes that frequently co-occur on the same device-day</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Antecedent</th><th>Consequent</th><th>Confidence</th><th>Lift</th><th>Support</th></tr>
            </thead>
            <tbody>
              {(rules.length > 0 ? rules : []).slice(0, 15).map((r, i) => (
                <tr key={i}>
                  <td>{r.antecedents}</td>
                  <td>{r.consequents}</td>
                  <td>{(r.confidence || 0).toFixed(3)}</td>
                  <td>{(r.lift || 0).toFixed(3)}</td>
                  <td>{(r.support || 0).toFixed(4)}</td>
                </tr>
              ))}
              {rules.length === 0 && <tr><td colSpan="5">Load detail tab for full rules</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid-2">
        {/* Markov Transitions */}
        <div className="panel">
          <h2>Markov Chain Transitions</h2>
          <p className="desc">Most probable error sequences</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>From Error</th><th>To Error</th><th>Probability</th><th>Count</th></tr>
              </thead>
              <tbody>
                {transitions.slice(0, 10).map((t, i) => (
                  <tr key={i}>
                    <td>{(t.from_error || '').replace('E0', 'E')}</td>
                    <td>{(t.to_error || '').replace('E0', 'E')}</td>
                    <td><strong>{(t.probability || 0).toFixed(4)}</strong></td>
                    <td>{t.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Severity Escalations */}
        <div className="panel">
          <h2>Severity Escalations</h2>
          <p className="desc">How errors escalate in severity</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>From</th><th>To</th><th>Count</th></tr>
              </thead>
              <tbody>
                {escalations.slice(0, 10).map((e, i) => (
                  <tr key={i}>
                    <td><span className={`badge ${(e.from_severity || '').toLowerCase()}`}>{e.from_severity}</span></td>
                    <td><span className={`badge ${(e.to_severity || '').toLowerCase()}`}>{e.to_severity}</span></td>
                    <td>{e.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Stationary Distribution */}
      {stationary.length > 0 && (
        <div className="panel">
          <h2>Stationary Distribution</h2>
          <p className="desc">Long-run probability of each error code (Markov steady state)</p>
          {stationary.slice(0, 12).map((s, i) => (
            <div className="bar-row" key={i}>
              <span className="bar-label">{(s.error_code || '').replace(/_/g, ' ')}</span>
              <div className="bar-track">
                <div className="bar-fill purple" style={{ width: `${Math.min((s.stationary_probability || 0) * 500, 100)}%` }}>
                  {(s.stationary_probability || 0).toFixed(4)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
