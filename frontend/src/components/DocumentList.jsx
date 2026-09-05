import DocumentCard from './DocumentCard.jsx'

function Shell({ children }) {
  return (
    <aside className="document-list" aria-label="Regulatory documents">
      {children}
    </aside>
  )
}

function Notice({ children, tone = 'muted' }) {
  const cls =
    tone === 'error'
      ? 'decision-red'
      : 'bg-card text-muted border border-border'
  return (
    <div className={`rounded-lg px-4 py-6 text-center text-sm ${cls}`}>
      {children}
    </div>
  )
}

export default function DocumentList({
  docs,
  selected,
  onSelect,
  loading,
  error,
  fetched,
  days,
  loadingMessage,
  emptyMessage,
}) {
  if (error && docs.length === 0) {
    return (
      <Shell>
        <Notice tone="error">Error: {error}</Notice>
      </Shell>
    )
  }

  if (loading) {
    return (
      <Shell>
        <Notice>
          <span className="spinner mr-2 align-middle" />
          {loadingMessage || 'Scraping MAS & processing documents…'}
        </Notice>
      </Shell>
    )
  }

  if (!fetched) {
    return (
      <Shell>
        <Notice>Click "Fetch latest" to load MAS documents.</Notice>
      </Shell>
    )
  }

  if (docs.length === 0) {
    return (
      <Shell>
        <Notice>
          {emptyMessage || `No MAS documents found in the last ${days} days.`}
        </Notice>
      </Shell>
    )
  }

  return (
    <Shell>
      {docs.map(doc => (
        <DocumentCard
          key={doc.id || doc.source_url}
          doc={doc}
          selected={selected?.source_url === doc.source_url}
          onSelect={onSelect}
        />
      ))}
    </Shell>
  )
}
