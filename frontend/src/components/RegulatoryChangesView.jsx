import { useMemo, useState } from 'react'
import Badge from './ui/Badge.jsx'
import AffectedDocumentsView from './AffectedDocumentsView.jsx'
import { IMPACT_META, impactLevel } from '../lib/impact.js'
import { affectedCountFor } from '../lib/mockAffected.js'

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
  const [opened, setOpened] = useState(null)

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

  if (opened) {
    return <AffectedDocumentsView regulation={opened} onBack={() => setOpened(null)} />
  }

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
              <th className="px-4 py-2.5 font-medium">Affected</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-muted">
                  No changes match these filters.
                </td>
              </tr>
            )}
            {rows.map(doc => {
              const level = impactLevel(doc)
              const affected = affectedCountFor(doc)
              return (
                <tr
                  key={doc.id || doc.source_url}
                  onClick={() => setOpened(doc)}
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
                  <td className="whitespace-nowrap px-4 py-2.5 align-top">
                    <button
                      onClick={e => {
                        e.stopPropagation()
                        setOpened(doc)
                      }}
                      className={
                        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[13px] font-medium ' +
                        (affected > 0
                          ? 'bg-decision-red-bg text-decision-red hover:underline'
                          : 'text-muted')
                      }
                      title="View affected documents and suggested fixes"
                    >
                      {affected} {affected === 1 ? 'document' : 'documents'}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
