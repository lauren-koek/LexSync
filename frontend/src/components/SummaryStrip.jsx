import { impactLevel } from '../lib/impact.js'
import MetricStrip from './ui/MetricStrip.jsx'

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

  return <MetricStrip items={stats.map(s => ({ ...s, tone: s.tone ? 'red' : undefined }))} />
}
