import { useState } from 'react'
import { runAnalysis } from '../api.js'
import AnalysisResults from './AnalysisResults.jsx'
import Button from './ui/Button.jsx'

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

  const fieldClass =
    'min-h-40 w-full resize-y rounded-lg border border-border bg-white p-3 text-sm leading-relaxed focus-visible:border-ring'

  return (
    <div className="flex flex-col gap-5">
      <div>
        <p className="eyebrow mb-1">Legal Resilience Engine</p>
        <p className="text-sm text-muted">
          Identify affected internal clauses, understand why, and preview a
          compliant redline.
        </p>
      </div>
      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
            <label className="text-sm font-medium" htmlFor="regulation-text">Regulatory update text</label>
            <textarea id="regulation-text" className={fieldClass} value={regulationText} onChange={event => setRegulationText(event.target.value)} />
            <label className="eyebrow" htmlFor="regulation-file">Regulation file</label>
            <input id="regulation-file" type="file" accept=".pdf,.txt" className="text-sm" onChange={event => setRegulationFile(event.target.files[0] || null)} />
            {regulationFile && <small className="text-muted">Using {regulationFile.name} instead of pasted text</small>}
          </div>
          <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
            <label className="text-sm font-medium" htmlFor="asset-text">Internal legal asset text</label>
            <textarea id="asset-text" className={fieldClass} value={internalAssetText} onChange={event => setInternalAssetText(event.target.value)} />
            <label className="eyebrow" htmlFor="asset-file">Internal asset file</label>
            <input id="asset-file" type="file" accept=".pdf,.txt" className="text-sm" onChange={event => setInternalAssetFile(event.target.files[0] || null)} />
            {internalAssetFile && <small className="text-muted">Using {internalAssetFile.name} instead of pasted text</small>}
          </div>
        </div>
        <Button className="self-start" type="submit" disabled={loading}>
          {loading && <span className="spinner" />}
          {loading ? 'Running analysis…' : 'Run Resilience Analysis'}
        </Button>
        {error && <div className="decision-red rounded-lg px-4 py-2 text-sm" role="alert">{error}</div>}
      </form>
      {result && <AnalysisResults result={result} />}
    </div>
  )
}
