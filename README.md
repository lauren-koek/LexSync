# LexSync

Singapore regulatory monitoring and legal resilience backend. It exposes a
FastAPI analysis API and retains the scheduled MAS-to-PostgreSQL pipeline.

## Structure

| Path | Purpose |
|---|---|
| `backend/main.py` | FastAPI application entry point |
| `backend/api/` | HTTP routes and Pydantic schemas |
| `backend/analysis/` | Request-local and CLI legal resilience workflow |
| `backend/storage/` | Private AWS-compatible storage for uploaded internal PDFs |
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
- `POST /api/v1/internal-documents` uploads and synchronously indexes a PDF.
- `GET /api/v1/internal-documents` lists the shared internal-document library.
- `POST /api/v1/internal-documents/search` performs semantic vector search.

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

## Internal document storage

Original PDFs are private objects in an S3-compatible bucket. Configure the
API service with `AWS_ENDPOINT_URL`, `S3_BUCKET_NAME`, `AWS_DEFAULT_REGION`,
`AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY`. Railway Bucket credentials
can be referenced directly into these variables. PDF access uses 15-minute
presigned URLs; no bucket object is public.

Uploads are limited to 10 MB and must contain extractable text. Image-only and
encrypted PDFs are rejected. Successful uploads are split into legal clauses,
embedded, and stored in PostgreSQL/pgvector before the request returns.

After a regulatory document is saved with OCR text, the MAS pipeline searches
the persistent internal index and saves suggested changes. Failed suggestion
generation is logged without rolling back regulatory ingestion and can be
retried from the UI.

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

- Add authentication and workspace ownership to the currently shared library.
- Move synchronous processing to a queue when upload volume requires it.
- `dispatch_updates(dry_run=True)` in `notify.py` is a documented extension
  point for real SMTP delivery — do not hardcode credentials, read them from
  environment variables.
