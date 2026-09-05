export default function DocumentCard({ doc, selected, onSelect }) {
  return (
    <div
      className={`doc-card ${selected ? 'selected' : ''}`}
      onClick={() => onSelect(doc)}
    >
      <div className="doc-card-title">{doc.title || 'Untitled'}</div>
      <div className="doc-card-meta">
        {doc.date && <span>{doc.date}</span>}
        {doc.doc_type && <span className="doc-card-type">{doc.doc_type}</span>}
        {doc.topic && <span>{doc.topic}</span>}
      </div>
    </div>
  )
}
