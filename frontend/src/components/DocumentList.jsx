import DocumentCard from './DocumentCard.jsx'

export default function DocumentList({ docs, selected, onSelect, loading, error, fetched, days }) {
  if (error) {
    return (
      <aside className="doc-list">
        <div className="doc-list-error">Error: {error}</div>
      </aside>
    )
  }

  if (loading) {
    return (
      <aside className="doc-list">
        <div className="doc-list-empty">
          <span className="spinner" /> Processing documents…
        </div>
      </aside>
    )
  }

  if (!fetched) {
    return (
      <aside className="doc-list">
        <div className="doc-list-empty">Click "Fetch Latest Updates" to load MAS documents.</div>
      </aside>
    )
  }

  if (docs.length === 0) {
    return (
      <aside className="doc-list">
        <div className="doc-list-empty">No MAS documents found in the last {days} days.</div>
      </aside>
    )
  }

  return (
    <aside className="doc-list">
      {docs.map(doc => (
        <DocumentCard
          key={doc.id || doc.source_url}
          doc={doc}
          selected={selected?.source_url === doc.source_url}
          onSelect={onSelect}
        />
      ))}
    </aside>
  )
}
