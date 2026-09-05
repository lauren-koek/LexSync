import { cn } from '../lib/utils.js'
import { IMPACT_META, impactLevel } from '../lib/impact.js'

const DOT = {
  high: 'bg-decision-red',
  medium: 'bg-decision-amber',
  low: 'bg-decision-green',
  none: 'bg-border-strong',
}

export default function DocumentCard({ doc, selected, onSelect }) {
  const level = impactLevel(doc)
  const meta = [doc.date, doc.doc_type, doc.topic].filter(Boolean)

  return (
    <button
      onClick={() => onSelect(doc)}
      className={cn('document-card', selected && 'document-card--selected')}
      title={level !== 'none' ? IMPACT_META[level].label : undefined}
    >
      <div className="flex items-start gap-2.5">
        <span
          className={cn('mt-1.5 h-2 w-2 shrink-0 rounded-full', DOT[level])}
          aria-hidden="true"
        />
        <div className="min-w-0 flex-1">
          <div className="line-clamp-2 text-[13.5px] font-medium leading-snug text-ink">
            {doc.title || 'Untitled'}
          </div>
          {meta.length > 0 && (
            <div className="mt-1 flex flex-wrap items-center gap-x-1.5 text-[12px] text-muted">
              {meta.map((part, i) => (
                <span key={i} className="inline-flex items-center gap-1.5">
                  {i > 0 && <span className="text-border-strong">·</span>}
                  <span className={i === 0 ? 'mono' : ''}>{part}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </button>
  )
}
