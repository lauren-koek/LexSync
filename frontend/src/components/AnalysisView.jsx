import { useState } from 'react'
import { runAnalysis } from '../api.js'
import AnalysisResults from './AnalysisResults.jsx'

const SAMPLE_REGULATION = `Section 12A. Mandatory AI Automated Decision Audit Logs.
Audit logs generated in connection with any automated decision-making system that processes personal data must be retained for a period of seven (7) years from the date of creation. Where an automated decision-making system is involved in a critical safety breach, the organisation must notify affected data subjects within twenty-four (24) hours of discovering the breach.`

const SAMPLE_ASSET = `Clause 8. Data Retention & Security.
The Vendor shall retain processing logs for a minimum of thirty-six (36) months from the date of creation. The Vendor shall notify the Company of any material data breach within seventy-two (72) hours of discovery.`

export default function AnalysisView() {
  const [regulationText, setRegulationText] = useState(SAMPLE_REGULATION)
  const [internalAssetText, setInternalAssetText] = useState(SAMPLE_ASSET)
  const [regulationFile, setRegulationFile] = useState(null)
  const [internalAssetFile, setInternalAssetFile] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(event) {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const nextResult = await runAnalysis({ regulationText, internalAssetText, regulationFile, internalAssetFile })
      setResult(nextResult)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="analysis-page">
      <div className="analysis-intro">
        <p className="eyebrow">Legal Resilience Engine</p>
        <h1>Resilience Analysis</h1>
        <p>Identify affected internal clauses, understand why, and preview a compliant redline.</p>
      </div>
      <form className="analysis-form" onSubmit={handleSubmit}>
        <div className="analysis-inputs">
          <div className="input-panel">
            <label htmlFor="regulation-text">Regulatory update text</label>
            <textarea id="regulation-text" value={regulationText} onChange={event => setRegulationText(event.target.value)} />
            <label className="file-label" htmlFor="regulation-file">Regulation file</label>
            <input id="regulation-file" type="file" accept=".pdf,.txt" onChange={event => setRegulationFile(event.target.files[0] || null)} />
            {regulationFile && <small>Using {regulationFile.name} instead of pasted text</small>}
          </div>
          <div className="input-panel">
            <label htmlFor="asset-text">Internal legal asset text</label>
            <textarea id="asset-text" value={internalAssetText} onChange={event => setInternalAssetText(event.target.value)} />
            <label className="file-label" htmlFor="asset-file">Internal asset file</label>
            <input id="asset-file" type="file" accept=".pdf,.txt" onChange={event => setInternalAssetFile(event.target.files[0] || null)} />
            {internalAssetFile && <small>Using {internalAssetFile.name} instead of pasted text</small>}
          </div>
        </div>
        <button className="analysis-submit" type="submit" disabled={loading}>
          {loading ? 'Running analysis…' : 'Run Resilience Analysis'}
        </button>
        {error && <div className="analysis-error" role="alert">{error}</div>}
      </form>
      {result && <AnalysisResults result={result} />}
    </main>
  )
}
