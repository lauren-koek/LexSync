import { useState } from 'react'
import { FileText, Search, Upload } from 'lucide-react'
import useInternalDocuments from '../hooks/useInternalDocuments.js'
import Button from './ui/Button.jsx'
import PageIntro from './ui/PageIntro.jsx'
import InternalDocumentDetail from './InternalDocumentDetail.jsx'

function bytes(value) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

export default function InternalDocumentsView() {
  const library = useInternalDocuments()
  const [openedId, setOpenedId] = useState(null)
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [query, setQuery] = useState('')
  const [uploading, setUploading] = useState(false)
  const [notice, setNotice] = useState('')

  if (openedId) return <InternalDocumentDetail documentId={openedId} onBack={() => setOpenedId(null)} onDeleted={() => { setOpenedId(null); library.resetSearch() }} />

  async function submitUpload(event) {
    event.preventDefault()
    if (!file) return
    setUploading(true); setNotice('')
    try {
      const result = await library.upload(file, title)
      setNotice(result.deduplicated ? 'This PDF was already indexed.' : 'Document indexed successfully.')
      setFile(null); setTitle(''); event.currentTarget.reset()
    } catch (err) { setNotice(err.message) }
    finally { setUploading(false) }
  }

  async function submitSearch(event) {
    event.preventDefault()
    if (query.trim()) await library.search(query.trim())
    else await library.resetSearch()
  }

  return <div className="view-stack">
    <PageIntro eyebrow="Shared knowledge base" title="Internal Documents" description="Upload policies and contracts, search their meaning, and review regulatory changes against the source." status={`${library.documents.length} documents shown`} />
    <div className="mb-4 grid gap-3 rounded-lg border border-border bg-card p-4 lg:grid-cols-2">
      <form onSubmit={submitUpload} className="flex flex-wrap items-end gap-2">
        <label className="min-w-0 flex-1 text-xs text-muted">Upload PDF<input aria-label="Upload PDF" type="file" accept="application/pdf,.pdf" onChange={event => setFile(event.target.files?.[0] || null)} className="mt-1 block w-full text-sm" /></label>
        <input aria-label="Document title" value={title} onChange={event => setTitle(event.target.value)} placeholder="Optional title" className="h-9 rounded-lg border border-border px-3 text-sm" />
        <Button disabled={!file || uploading}>{uploading ? <><span className="spinner" /> Indexing…</> : <><Upload size={15} /> Upload document</>}</Button>
      </form>
      <form onSubmit={submitSearch} className="flex items-end gap-2">
        <label className="flex-1 text-xs text-muted">Semantic search<input aria-label="Semantic search" value={query} onChange={event => setQuery(event.target.value)} placeholder="e.g. breach notification duties" className="mt-1 h-9 w-full rounded-lg border border-border px-3 text-sm" /></label>
        <Button variant="secondary" disabled={library.searching}><Search size={15} /> Search</Button>
      </form>
    </div>
    {(notice || library.error) && <div role="status" className="mb-3 rounded-lg border border-border bg-panel px-4 py-2 text-sm">{notice || library.error}</div>}
    <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-border bg-card">
      {library.loading ? <p className="p-8 text-center text-muted"><span className="spinner mr-2" /> Loading internal documents…</p> : library.documents.length === 0 ? <p className="p-10 text-center text-muted">No internal documents uploaded yet.</p> : <table className="w-full text-left text-sm"><thead className="sticky top-0 bg-panel text-muted"><tr><th className="px-4 py-3">Document</th><th className="px-4 py-3">Uploaded</th><th className="px-4 py-3">Size</th><th className="px-4 py-3">Clauses</th><th className="px-4 py-3">Status</th></tr></thead><tbody>{library.documents.map(doc => <tr key={doc.id} className="border-t border-border hover:bg-panel"><td className="p-0"><button aria-label={`Open ${doc.title}`} onClick={() => setOpenedId(doc.id)} className="flex w-full items-center gap-3 px-4 py-3 text-left"><FileText size={18} className="text-accent" /><span><strong className="block">{doc.title}</strong><span className="text-xs text-muted">{doc.filename}</span></span></button></td><td className="px-4 py-3 text-muted">{doc.created_at ? new Date(doc.created_at).toLocaleDateString() : '—'}</td><td className="px-4 py-3 text-muted">{bytes(doc.size_bytes || 0)}</td><td className="px-4 py-3">{doc.chunk_count ?? doc.excerpts?.length ?? 0}</td><td className="px-4 py-3 capitalize text-decision-green">{doc.status || 'indexed'}</td></tr>)}</tbody></table>}
    </div>
  </div>
}
