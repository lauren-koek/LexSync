import { useMemo, useState } from 'react'
import { ExternalLink, X } from 'lucide-react'
import Badge from './ui/Badge.jsx'
import DetailPanel from './DetailPanel.jsx'
import { IMPACT_META, impactLevel } from '../lib/impact.js'

function uniqueValues(docs, key) {
  return [...new Set(docs.map(d => d[key]).filter(Boolean))].sort()
}

function FilterSelect({ label, value, options, onChange }) {
  return (
    <label className="flex items-center gap-2 text-[13px] text-ink-soft">
      {label}
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="h-8 rounded-lg border border-border bg-white px-2 text-sm"
      >
        <option value="">All</option>
        {options.map(o => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  )
}

export default function RegulatoryChangesView({ documents }) {
  const { docs, initialLoading, initialError } = documents
  const [docType, setDocType] = useState('')
  const [topic, setTopic] = useState('')
  const [category, setCategory] = useState('')
  const [sortAsc, setSortAsc] = useState(false)
  const [selected, setSelected] = useState(null)

  const docTypes = useMemo(() => uniqueValues(docs, 'doc_type'), [docs])
  const topics = useMemo(() => uniqueValues(docs, 'topic'), [docs])
  const categories = useMemo(
    () => [...new Set(docs.flatMap(d => d.llm_categories || []))].sort(),
    [docs],
  )

  const rows = useMemo(() => {
    const filtered = docs.filter(d => {
      if (docType && d.doc_type !== docType) return false
      if (topic && d.topic !== topic) return false
      if (category && !(d.llm_categories || []).includes(category)) return false
      return true
    })
    return filtered.sort((a, b) => {
      const av = a.date || ''
      const bv = b.date || ''
      return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av)
    })
  }, [docs, docType, topic, category, sortAsc])

  if (initialLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted">
        <span className="spinner mr-2" /> Loading regulatory changes…
      </div>
    )
  }
  if (initialError) {
    return (
      <div className="decision-red rounded-lg px-4 py-6 text-sm">
        Error: {initialError}
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold">Regulatory Changes</h1>
        <p className="text-sm text-muted">
          Timeline of tracked MAS publications. {rows.length} shown.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
        <FilterSelect label="Type" value={docType} options={docTypes} onChange={setDocType} />
        <FilterSelect label="Topic" value={topic} options={topics} onChange={setTopic} />
        <FilterSelect label="Category" value={category} options={categories} onChange={setCategory} />
        <button
          onClick={() => setSortAsc(s => !s)}
          className="ml-auto text-[13px] font-medium text-accent-deep hover:underline"
        >
          Date {sortAsc ? '↑ oldest' : '↓ newest'}
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-border bg-card">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 bg-panel text-left">
            <tr className="text-muted">
              <th className="px-4 py-2.5 font-medium">Date</th>
              <th className="px-4 py-2.5 font-medium">Title</th>
              <th className="px-4 py-2.5 font-medium">Type</th>
              <th className="px-4 py-2.5 font-medium">Topic</th>
              <th className="px-4 py-2.5 font-medium">Impact</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-muted">
                  No changes match these filters.
                </td>
              </tr>
            )}
            {rows.map(doc => {
              const level = impactLevel(doc)
              return (
                <tr
                  key={doc.id || doc.source_url}
                  onClick={() => setSelected(doc)}
                  className="cursor-pointer border-t border-border hover:bg-panel"
                >
                  <td className="whitespace-nowrap px-4 py-2.5 align-top mono text-[13px] text-muted">
                    {doc.date || '—'}
                  </td>
                  <td className="px-4 py-2.5 align-top font-medium text-ink">
                    {doc.title || 'Untitled'}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 align-top text-ink-soft">
                    {doc.doc_type || '—'}
                  </td>
                  <td className="px-4 py-2.5 align-top text-ink-soft">
                    {doc.topic || '—'}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 align-top">
                    {level !== 'none' ? (
                      <Badge tone={IMPACT_META[level].tone}>
                        {IMPACT_META[level].label}
                      </Badge>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {selected && (
        <div
          className="fixed inset-0 z-40 flex justify-end bg-black/20"
          onClick={() => setSelected(null)}
        >
          <div
            className="flex h-full w-full max-w-lg flex-col bg-canvas p-4 shadow-xl"
            onClick={e => e.stopPropagation()}
          >
            <button
              onClick={() => setSelected(null)}
              className="mb-2 ml-auto inline-flex items-center gap-1 text-[13px] text-muted hover:text-ink"
            >
              Close <X size={14} />
            </button>
            <DetailPanel doc={selected} />
            {selected.source_url && (
              <a
                href={selected.source_url}
                target="_blank"
                rel="noreferrer"
                className="mt-3 inline-flex items-center gap-1 text-sm"
              >
                Open source <ExternalLink size={13} />
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
