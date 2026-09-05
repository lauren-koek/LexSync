export default function DetailPanel({ doc }) {
  if (!doc) {
    return (
      <main className="detail-panel">
        <div className="detail-empty">Select a document to view its summary.</div>
      </main>
    )
  }

  return (
    <main className="detail-panel">
      <h1 className="detail-title">{doc.title || 'Untitled'}</h1>

      <div className="detail-meta">
        {doc.date && <span>{doc.date}</span>}
        {doc.doc_type && <span>{doc.doc_type}</span>}
        {doc.topic && <span>{doc.topic}</span>}
        {doc.source_url && (
          <a className="detail-link" href={doc.source_url} target="_blank" rel="noreferrer">
            Source ↗
          </a>
        )}
      </div>

      {doc.llm_summary && (
        <div className="detail-section">
          <div className="detail-section-label">Summary</div>
          <p>{doc.llm_summary}</p>
        </div>
      )}

      {doc.llm_impact_check && (
        <div className="detail-section">
          <div className="detail-section-label">Impact Check</div>
          <p>{doc.llm_impact_check}</p>
        </div>
      )}

      {doc.llm_categories?.length > 0 && (
        <div className="detail-section">
          <div className="detail-section-label">Categories</div>
          <div className="tag-list">
            {doc.llm_categories.map(c => (
              <span key={c} className="tag">{c}</span>
            ))}
          </div>
        </div>
      )}

      {doc.tags?.length > 0 && (
        <div className="detail-section">
          <div className="detail-section-label">Tags</div>
          <div className="tag-list">
            {doc.tags.map(t => (
              <span key={t} className="tag">{t}</span>
            ))}
          </div>
        </div>
      )}

      {doc.applies_to?.length > 0 && (
        <div className="detail-section">
          <div className="detail-section-label">Applies To</div>
          <div className="tag-list">
            {doc.applies_to.map(a => (
              <span key={a} className="tag">{a}</span>
            ))}
          </div>
        </div>
      )}
    </main>
  )
}
