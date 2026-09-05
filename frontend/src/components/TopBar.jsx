import { RefreshCw, Search } from 'lucide-react'
import Button from './ui/Button.jsx'

export default function TopBar({ days, onDaysChange, onFetch, onRefresh, loading }) {
  return (
    <header className="feed-toolbar workspace-panel">
      <div>
        <span className="eyebrow">Update controls</span>
        <p className="mt-0.5 text-[12px] leading-snug text-muted">
          Fetch new publications or regenerate saved document analysis.
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
          title="Re-pull metadata and regenerate AI output using cached OCR where available"
        >
          <RefreshCw size={15} />
          Re-sync metadata
        </Button>
      </div>
    </header>
  )
}
