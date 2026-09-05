import { Network } from 'lucide-react'

export default function ImpactMapView() {
  return (
    <div className="flex h-full flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold">Impact Map</h1>
        <p className="text-sm text-muted">
          Trace how regulatory changes ripple through your internal documents.
        </p>
      </div>

      <div className="relative flex flex-1 items-center justify-center overflow-hidden rounded-lg border border-dashed border-border bg-card">
        {/* faint node/edge motif echoing the editorial map surface */}
        <svg
          className="pointer-events-none absolute inset-0 h-full w-full opacity-[0.12]"
          aria-hidden="true"
        >
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M40 0H0V40" fill="none" stroke="var(--color-accent)" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>

        <div className="relative max-w-md px-6 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-decision-green-bg text-accent-deep">
            <Network size={26} />
          </div>
          <h2 className="mb-1 text-base font-semibold">Coming soon</h2>
          <p className="text-sm leading-relaxed text-muted">
            The impact map unlocks once your internal documents are ingested.
            We'll render regulations, affected policies, and their propagation
            paths as an interactive graph.
          </p>
        </div>
      </div>
    </div>
  )
}
