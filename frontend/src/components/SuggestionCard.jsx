import { useState } from 'react'
import { Check, X } from 'lucide-react'
import { updateSuggestionStatus } from '../api.js'
import Badge from './ui/Badge.jsx'
import Button from './ui/Button.jsx'
import Redline from './Redline.jsx'

export default function SuggestionCard({ suggestion }) {
  const [item, setItem] = useState(suggestion)
  const [saving, setSaving] = useState(false)

  async function change(status) {
    // Mock fallback suggestions have no backend row; update them locally only.
    if (String(item.id).startsWith('mock-')) { setItem({ ...item, status }); return }
    setSaving(true)
    try { setItem(await updateSuggestionStatus(item.id, status)) }
    finally { setSaving(false) }
  }

  return (
    <article className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">Suggested redline</p>
          <h3 className="mt-1 text-sm">{item.regulation_clause_reference}</h3>
        </div>
        <Badge tone={item.impact_score >= 7 ? 'red' : 'amber'}>{Math.round(item.similarity_score * 100)}% match</Badge>
      </div>
      <p className="my-3 text-sm text-ink-soft">{item.legal_reasoning}</p>
      <Redline value={item.redline_diff} />
      {item.statutory_citations?.length > 0 && <p className="mt-2 text-xs text-muted">{item.statutory_citations.join(' · ')}</p>}
      <div className="mt-3 flex gap-2">
        {item.status === 'pending' ? <>
          <Button size="sm" disabled={saving} onClick={() => change('accepted')}><Check size={14} /> Accept</Button>
          <Button size="sm" variant="secondary" disabled={saving} onClick={() => change('dismissed')}><X size={14} /> Dismiss</Button>
        </> : <>
          <Badge tone={item.status === 'accepted' ? 'sage' : 'neutral'}>{item.status}</Badge>
          <button disabled={saving} className="text-xs text-muted hover:underline" onClick={() => change('pending')}>Undo</button>
        </>}
      </div>
    </article>
  )
}
