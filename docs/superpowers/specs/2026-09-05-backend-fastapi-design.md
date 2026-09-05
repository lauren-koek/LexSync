# Backend Package and FastAPI API Design

## Goal

Move LexSync's backend implementation into a `backend` package and expose the
legal resilience analysis through a FastAPI application that a separately
developed frontend can call over HTTP.

## Scope

The backend package owns the existing legal resilience demo pipeline and
relocates the production scraper-to-PostgreSQL pipeline, database
models/session, LLM integration, and scraper support code from `main` without
reimplementing them. The Streamlit application remains a development-only
client outside the backend package. Existing CLI entry
points remain available after their imports and paths are updated.

The API work covers request validation, analysis execution, response
serialization, health reporting, CORS configuration, and local run
documentation. It does not add authentication, persistence for API analysis
runs, background jobs, or a production frontend.

## Package layout

```text
backend/
  __init__.py
  main.py                 # FastAPI application
  api/
    __init__.py
    routes.py             # health and analysis HTTP routes
    schemas.py            # Pydantic request/response models
  analysis/
    __init__.py
    ingest.py             # clause extraction and chunking
    store.py              # embedding and semantic matching
    analyse.py            # impact analysis and redline generation
    notify.py             # propagation result and CLI rendering
    service.py             # in-memory request orchestration
  db/                    # existing main database layer, moved unchanged
  llm/                   # existing main LLM client/processor, moved unchanged
  scraper/               # existing main scraper/OCR support, moved unchanged
  pipeline.py             # scheduled scraper/OCR/LLM/DB pipeline
  run_pipeline.py         # legal resilience CLI demo
```

The Streamlit development UI remains at `app.py` and imports the moved
analysis modules through `backend.analysis`. Generated demo artifacts remain
at the repository root for CLI compatibility; API requests build and return
their results in memory and do not mutate those shared files.

## API contract

### `GET /api/v1/health`

Returns:

```json
{
  "status": "ok",
  "service": "lexsync-backend"
}
```

### `POST /api/v1/analysis`

Request body:

```json
{
  "regulation_text": "Section 12A...",
  "internal_asset_text": "Clause 8...",
  "regulation_id": "Uploaded_Regulation",
  "asset_id": "Uploaded_Internal_Asset"
}
```

`regulation_text` and `internal_asset_text` are required non-empty strings.
The two IDs are optional and default to the values shown above.

Response body:

```json
{
  "regulation_id": "Uploaded_Regulation",
  "asset_id": "Uploaded_Internal_Asset",
  "clause_count": 3,
  "match_count": 2,
  "report": [
    {
      "regulation": {},
      "asset": {},
      "similarity_score": 0.81,
      "analysis": {
        "is_affected": true,
        "impact_score": 7,
        "legal_reasoning": "...",
        "proposed_amended_clause": "...",
        "statutory_citations": ["Section 12A"]
      },
      "redline_diff": "...",
      "analysis_source": "offline_heuristic"
    }
  ],
  "propagation": {
    "dispatched": 1,
    "dry_run": true,
    "timestamp": "2026-09-05T00:00:00+00:00"
  }
}
```

The report retains the current JSON shape so the future frontend can render
the existing impact summary, redline, reasoning, and citation views without
depending on Python internals. `propagation` reports the existing dry-run
behavior; it does not send email or write `updated_playbook.md` during an API
request.

## Request flow

1. The route validates the request with Pydantic.
2. The service chunks the two supplied texts in memory.
3. The service builds a fresh in-memory vector index and finds related internal
   asset clauses.
4. The service analyzes each match and generates its redline.
5. The service computes a dry-run propagation summary without shared-file
   writes.
6. FastAPI serializes the result through response models.

The CLI pipeline keeps its current file-backed behavior. The production
scraper pipeline keeps its database-backed behavior and runs through its
existing command and container entrypoint.

## Configuration and compatibility

`FRONTEND_ORIGINS` is a comma-separated environment variable used by the
FastAPI CORS middleware. Its local default is `http://localhost:3000`.
`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, and `DATABASE_URL` retain their
existing meanings.

The API image is started with:

```bash
uvicorn backend.main:app --reload
```

Docker Compose runs two application containers from the same image:

```text
api       -> FastAPI on localhost:8000
pipeline  -> existing scheduled scraper/OCR/LLM/DB entrypoint
postgres  -> PostgreSQL 16
```

The `api` service overrides the image command with Uvicorn and exposes port
8000. The `pipeline` service explicitly uses `entrypoint.sh`, so adding the
API does not remove the scheduled production processing loop. Both services
receive the existing `DATABASE_URL`, OpenRouter settings, and
`PIPELINE_INTERVAL_HOURS`/`SCRAPER_DAYS` configuration where applicable.

The existing Streamlit development UI is started separately with:

```bash
streamlit run app.py
```

## Testing

Tests will verify the health response, required-field validation and empty
input rejection, the analysis response shape using the deterministic offline
path, and that API analysis does not write the shared demo artifacts. An
import smoke test will also verify that the moved CLI modules resolve through
the new `backend` package. Docker verification will build the image and
validate the Compose service configuration.
