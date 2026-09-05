import Redline from './Redline.jsx'
import MetricStrip from './ui/MetricStrip.jsx'

export default function AnalysisResults({ result }) {
  if (result.match_count === 0) {
    return <div className="analysis-notice" role="status"><strong>No semantically related internal assets were found for this regulation.</strong><span> Check the source text or try another internal asset, then run the comparison again.</span></div>
  }

  const affected = result.report.filter(entry => entry.analysis.is_affected)
  const highest = Math.max(0, ...result.report.map(entry => entry.analysis.impact_score))

  return (
    <section className="analysis-results" aria-label="Analysis results">
      <div className="results-decision">
        <p className="eyebrow">Decision</p>
        <h2>{affected.length} {affected.length === 1 ? 'clause requires' : 'clauses require'} action</h2>
        <p>Review the prioritized findings and proposed language before accepting any change.</p>
      </div>
      <MetricStrip items={[
        { label: 'Clauses scanned', value: result.clause_count },
        { label: 'Matches found', value: result.match_count },
        { label: 'Affected', value: affected.length, tone: affected.length ? 'red' : undefined },
        { label: 'Highest impact', value: `${highest}/10` },
      ]} />
      <div className="propagation-note">
        Dry-run propagation prepared for {result.propagation.dispatched} affected clause(s).
      </div>
      <table className="impact-summary" aria-label="Impact summary">
        <thead><tr><th>Asset</th><th>Clause</th><th>Similarity</th><th>Impact</th><th>Status</th></tr></thead>
        <tbody>
          {result.report.map((entry, index) => (
            <tr key={`summary-${entry.asset.doc_id || index}`}>
              <td>{entry.asset.title || 'Internal asset'}</td>
              <td>{entry.asset.clause_reference}</td>
              <td>{entry.similarity_score}</td>
              <td>{entry.analysis.impact_score}/10</td>
              <td>{entry.analysis.is_affected ? 'Affected' : 'Not affected'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {result.report.map((entry, index) => (
        <article className="impact-card" key={`${entry.asset.doc_id || 'asset'}-${entry.asset.clause_reference || index}`}>
          <div className="impact-heading">
            <div>
              <h2>{entry.asset.title || 'Internal asset'}</h2>
              <span>{entry.asset.clause_reference}</span>
            </div>
            <span className={`impact-badge ${entry.analysis.is_affected ? 'affected' : 'clear'}`}>
              {entry.analysis.is_affected ? 'Affected' : 'Not affected'} · {entry.analysis.impact_score}/10
            </span>
          </div>
          <div className="result-block">
            <h3>Redline</h3>
            <Redline value={entry.redline_diff} />
          </div>
          <div className="result-block">
            <h3>Legal reasoning</h3>
            <p>{entry.analysis.legal_reasoning}</p>
          </div>
          <div className="result-meta">
            <span>Citations: {entry.analysis.statutory_citations.join(', ') || 'N/A'}</span>
            <span>Similarity: {entry.similarity_score}</span>
            <span>Source: {entry.analysis_source}</span>
          </div>
        </article>
      ))}
    </section>
  )
}
