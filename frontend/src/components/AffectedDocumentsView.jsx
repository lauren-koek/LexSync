import { useState } from 'react'
import { ArrowLeft, Check, ExternalLink, Sparkles, X } from 'lucide-react'
import Badge from './ui/Badge.jsx'
import Button from './ui/Button.jsx'
import Redline from './Redline.jsx'
import { affectedDocumentsFor } from '../lib/mockAffected.js'

function confidenceTone(c) {
  if (c >= 0.85) return 'red'
  if (c >= 0.78) return 'amber'
  return 'sage'
}

function AffectedCard({ item }) {
  const [status, setStatus] = useState('pending') // pending | accepted | dismissed

  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">{item.docName}</h3>
          <p className="text-[13px] text-muted">{item.section}</p>
        </div>
        <Badge tone={confidenceTone(item.confidence)}>
          {Math.round(item.confidence * 100)}% match
        </Badge>
      </div>

      <div className="mb-3">
        <div className="eyebrow mb-1.5">Current clause</div>
        <p className="rounded-lg border border-border bg-canvas p-3 text-[13px] leading-relaxed text-ink-soft">
          {item.original}
        </p>
      </div>

      <div className="mb-4">
        <div className="eyebrow mb-1.5 flex items-center gap-1.5">
          <Sparkles size={12} /> Suggested redline
        </div>
        <Redline value={item.redline} />
      </div>

      {status === 'pending' ? (
        <div className="flex gap-2">
          <Button size="sm" onClick={() => setStatus('accepted')}>
            <Check size={14} /> Accept fix
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setStatus('dismissed')}>
            <X size={14} /> Dismiss
          </Button>
        </div>
      ) : (
        <div className="flex items-center gap-2 text-[13px] font-medium">
          <Badge tone={status === 'accepted' ? 'sage' : 'neutral'}>
            {status === 'accepted' ? 'Fix accepted' : 'Dismissed'}
          </Badge>
          <button
            className="text-muted hover:text-ink hover:underline"
            onClick={() => setStatus('pending')}
          >
            Undo
          </button>
        </div>
      )}
    </div>
  )
}

export default function AffectedDocumentsView({ regulation, onBack }) {
  const affected = affectedDocumentsFor(regulation)

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto">
      <button
        onClick={onBack}
        className="inline-flex w-fit items-center gap-1.5 text-[13px] font-medium text-accent-deep hover:underline"
      >
        <ArrowLeft size={14} /> Back to regulatory changes
      </button>

      {/* regulation context */}
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="eyebrow mb-1">Regulatory change</div>
        <h1 className="text-lg font-semibold leading-snug">
          {regulation.title || 'Untitled'}
        </h1>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-muted">
          {regulation.date && <span className="mono">{regulation.date}</span>}
          {regulation.doc_type && <span>{regulation.doc_type}</span>}
          {regulation.topic && <span>{regulation.topic}</span>}
          {regulation.source_url && (
            <a
              className="inline-flex items-center gap-1"
              href={regulation.source_url}
              target="_blank"
              rel="noreferrer"
            >
              Source <ExternalLink size={13} />
            </a>
          )}
        </div>
        {regulation.llm_summary && (
          <p className="mt-3 text-sm leading-relaxed text-ink-soft">
            {regulation.llm_summary}
          </p>
        )}
      </div>

      {/* mock disclaimer */}
      <div className="decision-amber flex items-start gap-2 rounded-lg px-4 py-2.5 text-[13px]">
        <Sparkles size={15} className="mt-0.5 shrink-0" />
        <span>
          Preview of automated impact detection. Affected documents and redlines
          shown here are illustrative — vector search over your internal
          documents will populate this once ingestion is enabled.
        </span>
      </div>

      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold">
          Affected documents
          <span className="ml-2 text-muted">({affected.length})</span>
        </h2>
      </div>

      {affected.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-card px-4 py-10 text-center text-sm text-muted">
          No internal documents appear to be affected by this change.
        </div>
      ) : (
        <div className="grid gap-4">
          {affected.map(item => (
            <AffectedCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}
