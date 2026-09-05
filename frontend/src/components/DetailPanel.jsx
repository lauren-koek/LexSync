import { ExternalLink } from 'lucide-react'
import Badge from './ui/Badge.jsx'
import { IMPACT_META, impactLevel } from '../lib/impact.js'

function Section({ label, children }) {
  return (
    <div className="border-t border-border pt-4">
      <div className="eyebrow mb-2">{label}</div>
      {children}
    </div>
  )
}

function cleanImpactCheck(text) {
  return text
    .split(/\r?\n/)
    .filter(line => line.trim().toLowerCase() !== 'impact check')
    .filter(line => !line.trim().toLowerCase().startsWith('effective date:'))
    .join('\n')
    .trim()
}

function Tags({ items }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map(t => (
        <Badge key={t}>{t}</Badge>
      ))}
    </div>
  )
}

export default function DetailPanel({ doc }) {
  if (!doc) {
    return (
      <main className="detail-panel detail-panel--empty">
        Select a document to inspect its summary and source.
      </main>
    )
  }

  const level = impactLevel(doc)
  const meta = IMPACT_META[level]
  const cleanedImpact = doc.llm_impact_check && cleanImpactCheck(doc.llm_impact_check)

  return (
    <main className="detail-panel">
      <div className="detail-panel__measure">
      <div className="mb-3 flex items-start justify-between gap-3">
        <h1 className="text-lg font-semibold leading-snug">
          {doc.title || 'Untitled'}
        </h1>
        {level !== 'none' && <Badge tone={meta.tone}>{meta.label}</Badge>}
      </div>

      <div className="mb-5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-muted">
        {doc.date && <span className="mono">{doc.date}</span>}
        {doc.doc_type && <span>{doc.doc_type}</span>}
        {doc.topic && <span>{doc.topic}</span>}
        {doc.effective_date && <span>Effective {doc.effective_date}</span>}
        {doc.source_url && (
          <a
            className="inline-flex items-center gap-1"
            href={doc.source_url}
            target="_blank"
            rel="noreferrer"
          >
            Source <ExternalLink size={13} />
          </a>
        )}
      </div>

      <div className="space-y-4">
        {doc.llm_summary && (
          <Section label="Summary">
            <p className="text-sm leading-relaxed text-ink-soft">
              {doc.llm_summary}
            </p>
          </Section>
        )}

        {cleanedImpact && (
          <Section label="Impact check">
            <p className="text-sm leading-relaxed text-ink-soft">
              {cleanedImpact}
            </p>
          </Section>
        )}

        {doc.llm_categories?.length > 0 && (
          <Section label="Categories">
            <Tags items={doc.llm_categories} />
          </Section>
        )}

        {doc.tags?.length > 0 && (
          <Section label="Tags">
            <Tags items={doc.tags} />
          </Section>
        )}

        {doc.issued_pursuant_to?.length > 0 && (
          <Section label="Issued pursuant to">
            <p className="text-sm">
              {doc.issued_pursuant_to.map((s, i) => (
                <span key={s.url || s.section}>
                  {i > 0 && ', '}
                  <a href={s.url} target="_blank" rel="noreferrer">
                    {s.section}
                  </a>
                </span>
              ))}
            </p>
          </Section>
        )}

        {doc.applies_to?.length > 0 && (
          <Section label="Applies to">
            <Tags items={doc.applies_to} />
          </Section>
        )}
      </div>
      </div>
    </main>
  )
}
