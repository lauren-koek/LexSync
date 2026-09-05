# LexSync

Singapore regulatory monitoring and legal resilience backend. It exposes a
FastAPI analysis API and retains the scheduled MAS-to-PostgreSQL pipeline.

## Structure

| Path | Purpose |
|---|---|
| `backend/main.py` | FastAPI application entry point |
| `backend/api/` | HTTP routes and Pydantic schemas |
| `backend/analysis/` | Request-local and CLI legal resilience workflow |
| `backend/scraper/src/pdf_ocr.py` | PDF text extraction (pdfplumber + Tesseract fallback) |
| `backend/db/` | SQLAlchemy 2.x models and session factory |
| `backend/llm/processor.py` | Per-document LLM summarise/categorise via OpenRouter |
| `backend/pipeline.py` | Scheduled ingestion pipeline CLI |
| `docker-compose.yml` | PostgreSQL 16 + API + scheduled pipeline |
| `requirements.txt` | Runtime dependencies |
| `requirements-dev.txt` | Local test dependencies |

## Quick Start with Docker

```bash
cp .env.example .env   # fill in OPENROUTER_API_KEY
docker compose up --build
```

The API is available at http://localhost:8000. Interactive OpenAPI docs are
available at http://localhost:8000/docs.

## API

Start it locally with:

```bash
make dev
```

`make dev` creates `.venv`, installs runtime and development dependencies,
and starts Uvicorn with reload on port 8000. Reloading is limited to
`backend/`, so virtual-environment changes do not restart the server. Run the
test suite with `make test`.

- `GET /api/v1/health` reports service health.
- `POST /api/v1/analysis` accepts regulation and internal-asset text and
  returns the analysis report without writing shared demo artifacts.

The future frontend should call
`http://localhost:8000/api/v1/analysis`. Configure allowed browser origins
with comma-separated `FRONTEND_ORIGINS` (default: `http://localhost:3000`).

## Running locally

```bash
pip install -r requirements.txt

# start only Postgres
docker compose up postgres -d

# run the pipeline
python -m backend.pipeline
```

See `backend/docs/pipeline.md` for stage-by-stage usage and
`backend/docs/database.md` for schema and DB management.

## Analysis status

The API contract and document-ingestion pipeline are in place. Semantic
matching is intentionally disabled until the PostgreSQL/pgvector-backed
internal-document index is implemented. For now, analysis requests return no
matches rather than initializing a local embedding model or vector database.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional — enables live LLM analysis instead of the offline heuristic fallback:

```bash
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY
export $(cat .env | xargs)
```

Without an API key, LLM processing is unavailable; use the pipeline's
`--skip-llm` option for ingestion-only runs.

## Other entry points

**CLI:**
```bash
python -m backend.run_pipeline
```

**Streamlit UI:**
```bash
streamlit run app.py
```
Then open http://localhost:8501.

## Extending beyond the hackathon

- Add the internal-document table and pgvector index through SQLAlchemy.
- Generate and store embeddings only for internal-team documents.
- Compare newly ingested regulatory material against that durable index.
- `dispatch_updates(dry_run=True)` in `notify.py` is a documented extension
  point for real SMTP delivery — do not hardcode credentials, read them from
  environment variables.
