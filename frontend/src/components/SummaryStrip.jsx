import { impactLevel } from '../lib/impact.js'

function withinDays(dateStr, days) {
  if (!dateStr) return false
  const d = new Date(dateStr)
  if (Number.isNaN(d.getTime())) return false
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000
  return d.getTime() >= cutoff
}

export default function SummaryStrip({ docs, days }) {
  const total = docs.length
  const recent = docs.filter(d => withinDays(d.date, days)).length
  const highImpact = docs.filter(d => impactLevel(d) === 'high').length

  const stats = [
    { label: 'Documents tracked', value: total },
    { label: `New in ${days} days`, value: recent },
    { label: 'High impact', value: highImpact, tone: highImpact > 0 },
  ]

  return (
    <div className="grid grid-cols-3 divide-x divide-border overflow-hidden rounded-lg border border-border bg-card">
      {stats.map(s => (
        <div key={s.label} className="px-5 py-4">
          <div className="eyebrow mb-1.5">{s.label}</div>
          <div
            className={
              'text-2xl font-semibold tabular-nums ' +
              (s.tone ? 'text-decision-red' : 'text-ink')
            }
          >
            {s.value}
          </div>
        </div>
      ))}
    </div>
  )
}
