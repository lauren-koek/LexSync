import Badge from './ui/Badge.jsx'
import { cn } from '../lib/utils.js'
import { IMPACT_META, impactLevel } from '../lib/impact.js'

export default function DocumentCard({ doc, selected, onSelect }) {
  const level = impactLevel(doc)
  const meta = IMPACT_META[level]

  return (
    <button
      onClick={() => onSelect(doc)}
      className={cn(
        'w-full rounded-lg border bg-card px-4 py-3 text-left transition-colors',
        selected
          ? 'border-accent bg-decision-green-bg/40 shadow-sm'
          : 'border-border hover:border-border-strong hover:bg-panel',
      )}
    >
      <div className="mb-1.5 flex items-start justify-between gap-2">
        <span className="text-sm font-medium leading-snug text-ink">
          {doc.title || 'Untitled'}
        </span>
        {level !== 'none' && (
          <Badge tone={meta.tone} className="shrink-0">
            {meta.label}
          </Badge>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-muted">
        {doc.date && <span className="mono">{doc.date}</span>}
        {doc.doc_type && (
          <span className="rounded bg-panel px-1.5 py-0.5 text-ink-soft">
            {doc.doc_type}
          </span>
        )}
        {doc.topic && <span>{doc.topic}</span>}
      </div>
    </button>
  )
}
