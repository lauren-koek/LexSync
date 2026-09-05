# LexSync Editorial Frontend Redesign — Design

**Date:** 2026-09-05
**Status:** Approved (design), pending implementation plan

## Goal

Rebuild the LexSync frontend around the editorial design language captured in
`sample_frontend/` (a Tailwind + shadcn/ui + Geist bundle). Deliver a
sidebar-driven app with three destinations — **Dashboard** (the regulatory
updates screen), **Regulatory Changes** (a table/timeline), and **Impact Map**
(placeholder until our own document ingestion exists). Keep the existing
Resilience Analysis view reachable.

## Decisions

- **Styling:** Adopt Tailwind CSS v4 + shadcn/ui primitives + Geist fonts to
  match the sample's stack. Port the sample's tokens into a Tailwind theme and a
  global `editorial-surfaces` layer.
- **Screens:** Dashboard and Regulatory Changes are live against current data;
  Impact Map is a styled placeholder.
- **Regulatory Changes presentation:** table/timeline (not a card grid).
- **Navigation:** `useState`-based view switching. No routing library.

## Design Tokens (from sample_frontend/index.BYl0jkVs.css)

- Canvas `#fafaf9`; cards `#fff`; borders `#d4d3cd` (secondary `#c9cac2`).
- Sage/olive accents: `#242822` (primary dark), `#607051`, `#536749`,
  `#6a795f` (focus ring), `#3a4933`.
- Decision semantics: red `#7b302b`, terracotta `#946e5d`,
  sage-green (`#607051`) for "aligned".
- Typography: Geist Sans (body), Geist Mono (IDs, citations, statutory refs).
- `--radius: .65rem`.

## App Shell

- **Sidebar** — `brand` block with `sample_frontend/lexsync-logo.jpg`,
  `navlabel` nav items (Dashboard, Regulatory Changes, Impact Map, Resilience
  Analysis), `sidebarinsight` footer note, `avatar`.
- **Main region** — `topbar` + active view.
- View state lives in `App.jsx` (`useState`), matching the current pattern.

## Screens

### Dashboard (= Regulatory Updates)
- Summary strip (`summarystrip`): total documents, new-in-window count,
  high-impact count (derived from `llm_impact_check`/categories).
- Controls (`topbar`): lookback `days` selector, Fetch Latest, Refresh.
- `DocumentList` (restyled cards) → `DetailPanel`.
- Data: `GET /api/v1/documents` on load; `POST /api/v1/updates` for fetch/refresh.

### Regulatory Changes
- Table/timeline of the same documents, columns: date, title, type, topic,
  categories/tags, impact indicator.
- Filters: doc_type, topic, category. Sort by date (default desc).
- Row selection opens the same `DetailPanel` (as a side panel/Sheet).
- Consumes the shared document data — no separate fetch.

### Impact Map (placeholder)
- Editorial styling using `.mapcontainer` / `.legend` classes.
- "Coming soon — awaiting document ingestion" empty state. No graph logic.

### Resilience Analysis
- Existing `AnalysisView` / `Redline`, restyled to editorial surfaces,
  reachable from the sidebar.

## Data Flow

- New `useDocuments()` hook owns `docs`, `loading`, `error`, `days`, and
  `runFetch({ refresh })`. Logic moves out of `UpdatesView`.
- Dashboard and Regulatory Changes both consume `useDocuments()` so they share
  one fetched dataset.
- Impact Map does not consume document data yet.

## Component Plan

- `App.jsx` — sidebar shell + `useState` view router; owns/hosts `useDocuments`.
- New: `Sidebar.jsx`, `SummaryStrip.jsx`, `RegulatoryChangesView.jsx`,
  `ImpactMapView.jsx`, `hooks/useDocuments.js`, shadcn primitives under
  `components/ui/` (Button, Card, Badge, Input, Select, Table, Sheet).
- Restyle existing: `TopBar`, `DocumentList`, `DocumentCard`, `DetailPanel`,
  `UpdatesView` (becomes Dashboard body).

## Error Handling

- Preserve current semantics (inline alerts, empty/loading states); restyle to
  editorial `.notice` + spinner. No behavior changes to API error surfacing.

## Build / Tooling

- Add Tailwind v4, `@tailwindcss/vite` (or PostCSS), shadcn/ui deps, Geist font
  package. Vite and vitest configs preserved (Tailwind must not break jsdom
  tests).
- `esbuild` override (`0.21.5`) preserved for Linux `npm ci`.

## Testing

- Update existing vitest suites for the new structure.
- Add render tests: Sidebar nav switching, SummaryStrip counts,
  RegulatoryChangesView filtering/sorting.

## Out of Scope

- Impact Map graph rendering and interactions.
- Any backend/API changes.
- Document ingestion of our own documents.
