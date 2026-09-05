import { useEffect, useState } from 'react'
import { ArrowLeft, ExternalLink } from 'lucide-react'
import { fetchRegulatorySuggestions } from '../api.js'
import SuggestionCard from './SuggestionCard.jsx'

export default function AffectedDocumentsView({ regulation, onBack }) {
  const [suggestions, setSuggestions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    fetchRegulatorySuggestions(regulation.id)
      .then(items => active && setSuggestions(items))
      .catch(err => active && setError(err.message))
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [regulation.id])

  return <div className="flex h-full flex-col gap-4 overflow-auto">
    <button onClick={onBack} className="inline-flex w-fit items-center gap-1.5 text-[13px] font-medium text-accent-deep hover:underline"><ArrowLeft size={14} /> Back to regulatory changes</button>
    <div className="rounded-lg border border-border bg-card p-5">
      <div className="eyebrow mb-1">Regulatory change</div>
      <h1 className="text-lg font-semibold leading-snug">{regulation.title || 'Untitled'}</h1>
      <div className="mt-2 flex flex-wrap items-center gap-3 text-[13px] text-muted">
        {regulation.date && <span className="mono">{regulation.date}</span>}
        {regulation.doc_type && <span>{regulation.doc_type}</span>}
        {regulation.topic && <span>{regulation.topic}</span>}
        {regulation.source_url && <a className="inline-flex items-center gap-1" href={regulation.source_url} target="_blank" rel="noreferrer">Source <ExternalLink size={13} /></a>}
      </div>
      {regulation.llm_summary && <p className="mt-3 text-sm leading-relaxed text-ink-soft">{regulation.llm_summary}</p>}
    </div>
    <div className="flex items-baseline justify-between"><h2 className="text-sm font-semibold">Affected clauses <span className="ml-2 text-muted">({suggestions.length})</span></h2></div>
    {loading ? <p className="p-6 text-center text-muted"><span className="spinner mr-2" /> Loading suggestions…</p> : error ? <div role="alert" className="decision-red rounded-lg p-4">{error}</div> : suggestions.length === 0 ? <div className="rounded-lg border border-dashed border-border bg-card px-4 py-10 text-center text-sm text-muted">No internal documents appear to be affected by this change.</div> : <div className="grid gap-4">{suggestions.map(item => <SuggestionCard key={item.id} suggestion={item} />)}</div>}
  </div>
}
