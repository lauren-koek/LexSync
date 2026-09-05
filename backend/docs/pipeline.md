# Pipeline

## End-to-end flow

```
mas_regulations_scraper.py
        |
        | backend/scraper/output/mas_regulations_and_guidance.json
        v
   pdf_ocr.py  (download_and_ocr)
        |
        | backend/scraper/output/pdfs/*.pdf
        | backend/scraper/output/ocr/*.txt  (cache)
        v
  llm/processor.py  (process_document)
        |
        | summary, categories, impact_check
        v
   db/  (upsert into documents table)
```

`backend/pipeline.py` drives all three stages sequentially per document. Each stage is skippable via CLI flags.

Semantic comparison is a later database-backed stage. Internal-team documents
will be embedded into PostgreSQL using pgvector; ingested regulatory PDFs and
their LLM recommendations remain ordinary relational data.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string, e.g. `postgresql://lexsync:lexsync@localhost:5432/lexsync` |
| `OPENROUTER_API_KEY` | Yes (unless `--skip-llm`) | API key for OpenRouter |
| `OPENROUTER_MODEL` | No | Model ID to use. Defaults to whatever `llm/client.py` sets if unset |

Put these in `.env` at the repo root — `python-dotenv` loads it automatically.

## Running the full pipeline with docker-compose

```bash
cp .env.example .env   # set OPENROUTER_API_KEY (and optionally OPENROUTER_MODEL)
docker compose up --build
```

This starts Postgres, the FastAPI service, and the scheduled pipeline. Scraper
output under `backend/scraper/output/` is bind-mounted into the pipeline
container.

## Running stages independently

### 1. Scraper only

```bash
python -m backend.scraper.src.mas_regulations_scraper
```

Produces `backend/scraper/output/mas_regulations_and_guidance.json` when the
optional scraper entry module is present.

### 2. Pipeline — OCR + LLM + DB

```bash
python -m backend.pipeline
```

Uses default paths. Override with flags (see below).

### 3. Skip OCR (re-process existing records with LLM only)

```bash
python -m backend.pipeline --skip-ocr
```

### 4. Skip LLM (ingest metadata and OCR text without LLM analysis)

```bash
python -m backend.pipeline --skip-llm
```

### 5. Dry-run on a small batch

```bash
python -m backend.pipeline --limit 5
```

## CLI flags for pipeline.py

| Flag | Default | Description |
|---|---|---|
| `--json PATH` | `backend/scraper/output/mas_regulations_and_guidance.json` | Path to scraper JSON output |
| `--pdf-dir PATH` | `backend/scraper/output/pdfs` | Directory for downloaded PDFs |
| `--ocr-dir PATH` | `backend/scraper/output/ocr` | Directory for cached OCR text files |
| `--limit N` | (none) | Process only the first N documents |
| `--skip-ocr` | false | Skip PDF download and OCR |
| `--skip-llm` | false | Skip LLM summarisation and categorisation |
