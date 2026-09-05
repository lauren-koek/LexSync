import { useRef, useState } from 'react'
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
  const fileInputRef = useRef(null)

  if (openedId) return <InternalDocumentDetail documentId={openedId} onBack={() => setOpenedId(null)} onDeleted={() => { setOpenedId(null); library.resetSearch() }} />

  async function submitUpload(event) {
    event.preventDefault()
    if (!file) return
    setUploading(true); setNotice('')
    try {
      const result = await library.upload(file, title)
      setNotice(result.deduplicated ? 'This PDF was already indexed.' : 'Document indexed successfully.')
      setFile(null); setTitle('')
      if (fileInputRef.current) fileInputRef.current.value = ''
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
      <form onSubmit={submitUpload} className="rounded-lg border border-border bg-panel p-4">
        <div
          onDragOver={event => event.preventDefault()}
          onDrop={event => {
            event.preventDefault()
            const droppedFile = event.dataTransfer.files?.[0]
            if (droppedFile) setFile(droppedFile)
          }}
          className="flex min-h-28 flex-col items-center justify-center rounded-lg border border-dashed border-border bg-card px-4 py-5 text-center"
        >
          <input ref={fileInputRef} aria-label="Choose a PDF" type="file" accept="application/pdf,.pdf" onChange={event => setFile(event.target.files?.[0] || null)} className="sr-only" />
          <Upload size={22} className="mb-2 text-accent" />
          {file ? <>
            <strong className="max-w-full truncate text-sm">{file.name}</strong>
            <span className="mt-1 text-xs text-muted">{bytes(file.size)}</span>
            <button type="button" onClick={() => fileInputRef.current?.click()} className="mt-2 text-xs font-medium text-accent hover:underline">Change file</button>
          </> : <>
            <button type="button" onClick={() => fileInputRef.current?.click()} className="text-sm font-semibold text-accent hover:underline">Choose PDF</button>
            <span className="mt-1 text-xs text-muted">or drag and drop it here</span>
            <span className="mt-2 text-xs text-muted">PDF files only</span>
          </>}
        </div>
        {file && <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="min-w-48 flex-1 text-xs text-muted">Document title (optional)<input aria-label="Document title" value={title} onChange={event => setTitle(event.target.value)} placeholder={file.name.replace(/\.pdf$/i, '')} className="mt-1 h-9 w-full rounded-lg border border-border bg-card px-3 text-sm text-foreground" /></label>
          <Button disabled={uploading}>{uploading ? <><span className="spinner" /> Extracting and indexing…</> : <><Upload size={15} /> Upload and index</>}</Button>
        </div>}
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
