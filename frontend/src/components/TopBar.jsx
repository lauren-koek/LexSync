import { RefreshCw, Search } from 'lucide-react'
import Button from './ui/Button.jsx'

export default function TopBar({ days, onDaysChange, onFetch, onRefresh, loading }) {
  return (
    <header className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-border bg-card px-4 py-3">
      <div>
        <span className="eyebrow">MAS regulatory feed</span>
        <p className="mt-0.5 text-[12px] leading-snug text-muted">
          Fetch new pulls fresh documents. Re-sync metadata updates scraped
          fields on saved documents without re-running OCR or AI analysis.
        </p>
      </div>
      <div className="ml-auto flex flex-wrap items-end gap-3">
        <label className="flex items-center gap-2 text-[13px] text-ink-soft">
          Last
          <input
            type="number"
            min="1"
            max="365"
            value={days}
            onChange={e => onDaysChange(Number(e.target.value))}
            disabled={loading}
            className="h-8 w-16 rounded-lg border border-border bg-white px-2 text-center text-sm tabular-nums disabled:opacity-50"
          />
          days
        </label>
        <Button
          onClick={onFetch}
          disabled={loading}
          title="Scrape MAS and process any new documents (existing ones are served from cache)"
        >
          {loading ? <span className="spinner" /> : <Search size={15} />}
          {loading ? 'Fetching…' : 'Fetch new'}
        </Button>
        <Button
          variant="secondary"
          onClick={onRefresh}
          disabled={loading}
          title="Re-pull scraped fields for documents already saved; keeps cached OCR and AI output"
        >
          <RefreshCw size={15} />
          Re-sync metadata
        </Button>
      </div>
    </header>
  )
}
