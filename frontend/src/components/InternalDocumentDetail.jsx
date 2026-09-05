import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, RefreshCw, Trash2 } from 'lucide-react'
import { deleteInternalDocument, fetchInternalDocument, fetchInternalDocumentPdfUrl, reanalyzeInternalDocument } from '../api.js'
import Button from './ui/Button.jsx'
import SuggestionCard from './SuggestionCard.jsx'

export default function InternalDocumentDetail({ documentId, onBack, onDeleted }) {
  const [document, setDocument] = useState(null)
  const [pdfUrl, setPdfUrl] = useState('')
  const [filter, setFilter] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function load() {
    setError(null)
    try {
      const [detail, pdf] = await Promise.all([
        fetchInternalDocument(documentId), fetchInternalDocumentPdfUrl(documentId),
      ])
      setDocument(detail)
      setPdfUrl(pdf.url)
    } catch (err) { setError(err.message) }
  }

  useEffect(() => { load() }, [documentId])
  const chunks = useMemo(() => (document?.chunks || []).filter(chunk =>
    `${chunk.clause_reference} ${chunk.content}`.toLowerCase().includes(filter.toLowerCase())
  ), [document, filter])

  async function reanalyze() {
    setBusy(true)
    try { await reanalyzeInternalDocument(documentId); await load() }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  async function remove() {
    if (!window.confirm(`Delete ${document.title}?`)) return
    setBusy(true)
    try { await deleteInternalDocument(documentId); onDeleted(documentId) }
    catch (err) { setError(err.message); setBusy(false) }
  }

  if (!document && !error) return <div className="flex h-full items-center justify-center text-muted"><span className="spinner mr-2" /> Loading document…</div>
  if (!document) return <div role="alert" className="decision-red rounded-lg p-4">{error}</div>

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="inline-flex items-center gap-1 text-sm font-medium text-accent-deep"><ArrowLeft size={15} /> Back to documents</button>
        <div className="ml-auto flex gap-2">
          <Button size="sm" variant="secondary" disabled={busy} onClick={reanalyze}><RefreshCw size={14} /> Re-run analysis</Button>
          <Button size="sm" variant="secondary" disabled={busy} onClick={remove}><Trash2 size={14} /> Delete</Button>
        </div>
      </div>
      {error && <div role="alert" className="decision-red rounded-lg px-4 py-2 text-sm">{error}</div>}
      <div className="internal-detail-grid min-h-0 flex-1">
        <section className="overflow-hidden rounded-lg border border-border bg-card">
          {pdfUrl ? <iframe title={`${document.title} PDF`} src={pdfUrl} className="h-full min-h-[32rem] w-full" /> : <p className="p-6 text-muted">PDF preview unavailable.</p>}
        </section>
        <section className="overflow-y-auto rounded-lg border border-border bg-panel p-5">
          <p className="eyebrow">Internal document</p>
          <h1 className="mt-1 text-xl">{document.title}</h1>
          <p className="mt-1 text-sm text-muted">{document.filename} · {document.chunk_count} clauses</p>
          <input aria-label="Filter extracted clauses" value={filter} onChange={event => setFilter(event.target.value)} placeholder="Filter extracted clauses…" className="mt-5 h-9 w-full rounded-lg border border-border bg-white px-3 text-sm" />
          <div className="mt-4 space-y-3">
            {chunks.map(chunk => <article key={chunk.id} className="rounded-lg border border-border bg-card p-4"><h2 className="text-sm">{chunk.clause_reference}</h2><p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink-soft">{chunk.content}</p></article>)}
          </div>
          <h2 className="mb-3 mt-6 text-sm">Suggested changes ({document.suggestions.length})</h2>
          <div className="space-y-3">{document.suggestions.map(item => <SuggestionCard key={item.id} suggestion={item} />)}</div>
        </section>
      </div>
    </div>
  )
}
