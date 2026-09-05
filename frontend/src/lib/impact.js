// Derive an editorial impact level from a document's LLM impact check.
// The backend returns a free-text `llm_impact_check`; we bucket it into
// high / medium / low / none for consistent visual treatment.

const HIGH = /\b(high|significant|material|critical|directly affect|must)\b/i
const MEDIUM = /\b(medium|moderate|potential|may|possible|review)\b/i

export function impactLevel(doc) {
  const text = doc?.llm_impact_check
  if (!text) return 'none'
  if (HIGH.test(text)) return 'high'
  if (MEDIUM.test(text)) return 'medium'
  return 'low'
}

export const IMPACT_META = {
  high: { label: 'High impact', tone: 'red' },
  medium: { label: 'Medium impact', tone: 'amber' },
  low: { label: 'Low impact', tone: 'sage' },
  none: { label: 'Not assessed', tone: 'neutral' },
}
