# Unified React Updates and Resilience Experience

**Date:** 2026-09-05  
**Status:** Approved

## Objective

Turn the existing React MAS updates viewer into the single LexSync frontend. It
will automatically display documents already stored in PostgreSQL and recreate
the Legal Resilience Engine experience from commit
`6cda92327981c0d2f0ae4ba2946d232ab0ba1777` end to end.

The historical behavior is preserved: users manually paste or upload a new
regulation and an internal legal asset. Saved MAS documents are browsable but
are not automatically passed into resilience analysis.

## User Experience

The application has two primary views:

1. **Regulatory Updates** — browse saved database documents and request fresh
   MAS updates.
2. **Resilience Analysis** — compare a regulation with an internal legal asset
   and inspect semantic matches, impact reasoning, citations, and redlines.

Navigation preserves the state of both views. Errors in one view do not clear
successful results in the other.

### Regulatory Updates

On application startup, the frontend loads up to 50 existing database
documents, ordered by publication date descending. The first result is
selected automatically. An empty database displays a specific empty state.

The existing lookback selector and **Fetch Latest Updates** action remain.
Fetching runs the existing MAS scrape/process/store workflow and replaces the
visible document list with that request's results. Scrape loading and errors
are distinct from initial database loading and errors.

### Resilience Analysis

The analysis view starts with the sample regulation and internal asset from
the historical demo. Each input supports editable pasted text and an optional
`.txt` or `.pdf` upload. When a file is supplied, extracted file text takes
precedence over the pasted text, matching the historical Streamlit behavior.

After submission, the frontend displays:

- clauses scanned, matches found, affected clauses, and highest impact score;
- one summary row per matched clause;
- affected/not-affected status and severity;
- formatted word-level redlines (deletions and additions);
- legal reasoning, statutory citations, similarity, and analysis source; and
- the dry-run propagation count returned by the analysis service.

If no clauses meet the semantic threshold, the UI displays the historical
no-match message rather than treating the response as an error.

## Backend Design

### `GET /api/v1/documents`

Returns at most 50 rows from the `documents` table, ordered by publication
date descending, with deterministic fallback ordering by creation time. It
uses the existing `DocumentResponse` contract.

Database access lives in a focused query function rather than in the route.
The query opens and closes its own SQLAlchemy session through `get_session()`.

### Existing `POST /api/v1/updates`

Its public contract remains unchanged. It continues to scrape MAS, filter by
the requested lookback, reuse cached processing, persist new results, and
return matching documents.

### Existing `POST /api/v1/analysis`

Its JSON request and response remain unchanged for existing clients.

### `POST /api/v1/analysis/upload`

A multipart endpoint supports the historical file-upload behavior. Fields:

- `regulation_text`: optional pasted text;
- `internal_asset_text`: optional pasted text;
- `regulation_file`: optional `.txt` or `.pdf` file;
- `internal_asset_file`: optional `.txt` or `.pdf` file;
- `regulation_id` and `asset_id`: optional identifiers with current defaults.

Each side must provide non-blank pasted text or a supported file. Uploaded
files take precedence. Text extraction reuses the legal ingestion layer and
uses request-scoped temporary files, which are removed after extraction.
Unsupported, empty, or unreadable files return a clear 4xx error. The endpoint
then calls the same request-local `run_analysis()` service as the JSON route.

`python-multipart` becomes a runtime dependency for FastAPI multipart parsing.

## Frontend Design

The existing React 18/Vite/plain-CSS stack remains. `App` owns the selected
view and persistent state for each workflow.

New or revised units:

- `api.js` exposes `fetchDocuments()`, `fetchUpdates(days)`, and multipart
  `runAnalysis(...)` calls.
- Navigation switches between Updates and Analysis without a full reload.
- The updates view reuses `DocumentList`, `DocumentCard`, and `DetailPanel`.
- The analysis form owns text/file inputs and submission state.
- Analysis summary and clause-result components render the backend contract;
  a dedicated redline renderer converts `[-deleted-]` and `{+added+}` markers
  to safe React elements without injecting raw HTML.

The frontend never performs legal extraction, semantic matching, or LLM logic.

## Error Handling

- Database-load failures display an updates-panel error while preserving the
  ability to run analysis.
- Scrape failures leave previously loaded database documents visible.
- Analysis validation and server errors display beside the analysis form and
  retain the user's inputs.
- A new analysis request does not discard the previous successful report
  until a replacement succeeds.
- Network responses with invalid JSON produce a readable client error.

## Compatibility and Security

- Existing API paths and JSON contracts remain backward-compatible.
- Upload filenames are never used as durable filesystem paths.
- Temporary files are request-scoped and removed after extraction.
- Redlines are rendered as React text nodes, preventing HTML injection.
- The current 50-document cap and CORS/environment configuration remain.

## Verification

Backend tests cover database ordering and limits, route serialization,
multipart validation, `.txt` and `.pdf` extraction paths, file-over-text
precedence, and delegation to the existing analysis service.

Frontend tests cover initial database loading, navigation and retained state,
fresh-update behavior, multipart submission, loading/error/no-match states,
and analysis/redline rendering. Verification includes the full Python suite
and a production Vite build.

## Out of Scope

- Automatically analyzing saved MAS documents.
- Persisting analysis reports or uploaded internal assets.
- Authentication, pagination, and background job orchestration.
- Replacing the existing in-memory Qdrant semantic index.
