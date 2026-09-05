import { useState } from 'react'
import { runAnalysis } from '../api.js'
import AnalysisResults from './AnalysisResults.jsx'
import Button from './ui/Button.jsx'
import PageIntro from './ui/PageIntro.jsx'
import WorkspacePanel from './ui/WorkspacePanel.jsx'

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
    <div className="view-stack">
      <PageIntro eyebrow="Legal resilience engine" title="Resilience Analysis" description="Compare a regulatory update with an internal legal asset to identify exposure, understand why it matters, and prepare a compliant redline." status={result ? 'Analysis complete' : 'Ready to compare'} />
      <ol className="analysis-progress" aria-label="Analysis progress">
        {['Inputs', 'Analyse', 'Findings', 'Decision'].map((step, index) => <li className={index === 0 && !result ? 'is-current' : result ? 'is-complete' : ''} key={step}><span>{index + 1}</span>{step}</li>)}
      </ol>
      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <WorkspacePanel className="analysis-inputs">
          <div className="analysis-input">
            <p className="eyebrow">01 · Regulation</p>
            <label className="text-sm font-medium" htmlFor="regulation-text">Regulatory update text</label>
            <textarea id="regulation-text" className={fieldClass} value={regulationText} onChange={event => setRegulationText(event.target.value)} />
            <label className="text-xs font-medium text-ink-soft" htmlFor="regulation-file">Or upload regulation file</label>
            <input id="regulation-file" aria-label="Regulation file" type="file" accept=".pdf,.txt" className="text-sm" onChange={event => setRegulationFile(event.target.files[0] || null)} />
            {regulationFile && <small className="file-precedence">{regulationFile.name} replaces the pasted regulation text for this analysis.</small>}
          </div>
          <div className="analysis-input">
            <p className="eyebrow">02 · Internal asset</p>
            <label className="text-sm font-medium" htmlFor="asset-text">Internal legal asset text</label>
            <textarea id="asset-text" className={fieldClass} value={internalAssetText} onChange={event => setInternalAssetText(event.target.value)} />
            <label className="text-xs font-medium text-ink-soft" htmlFor="asset-file">Or upload internal asset</label>
            <input id="asset-file" aria-label="Internal asset file" type="file" accept=".pdf,.txt" className="text-sm" onChange={event => setInternalAssetFile(event.target.files[0] || null)} />
            {internalAssetFile && <small className="file-precedence">{internalAssetFile.name} replaces the pasted internal asset text for this analysis.</small>}
          </div>
        </WorkspacePanel>
        <Button className="self-start" type="submit" disabled={loading}>
          {loading && <span className="spinner" />}
          {loading ? 'Running analysis…' : 'Run Resilience Analysis'}
        </Button>
        {error && <div className="decision-red rounded-lg px-4 py-3 text-sm" role="alert">Analysis could not complete: {error}. Your previous result remains available; try again when ready.</div>}
      </form>
      {result && <AnalysisResults result={result} />}
    </div>
  )
}
