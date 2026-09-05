# Pipeline

## End-to-end flow

```
mas_regulations_scraper.py
        |
        | scraper/output/mas_regulations_and_guidance.json
        v
   pdf_ocr.py  (download_and_ocr)
        |
        | scraper/output/pdfs/*.pdf
        | scraper/output/ocr/*.txt  (cache)
        v
  llm/processor.py  (process_document)
        |
        | summary, categories, impact_check
        v
   db/  (upsert into documents table)
```

`pipeline.py` drives all three stages sequentially per document. Each stage is skippable via CLI flags.

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
docker-compose up
```

This starts Postgres, waits for it to be healthy, then runs the pipeline container. Scraper output under `scraper/output/` is bind-mounted into the container.

## Running stages independently

### 1. Scraper only

```bash
python -m scraper.src.mas_regulations_scraper
```

Produces `scraper/output/mas_regulations_and_guidance.json`.

### 2. Pipeline — OCR + LLM + DB

```bash
python pipeline.py
```

Uses default paths. Override with flags (see below).

### 3. Skip OCR (re-process existing records with LLM only)

```bash
python pipeline.py --skip-ocr
```

### 4. Skip LLM (ingest metadata and OCR text without LLM analysis)

```bash
python pipeline.py --skip-llm
```

### 5. Dry-run on a small batch

```bash
python pipeline.py --limit 5
```

## CLI flags for pipeline.py

| Flag | Default | Description |
|---|---|---|
| `--json PATH` | `scraper/output/mas_regulations_and_guidance.json` | Path to scraper JSON output |
| `--pdf-dir PATH` | `scraper/output/pdfs` | Directory for downloaded PDFs |
| `--ocr-dir PATH` | `scraper/output/ocr` | Directory for cached OCR text files |
| `--limit N` | (none) | Process only the first N documents |
| `--skip-ocr` | false | Skip PDF download and OCR |
| `--skip-llm` | false | Skip LLM summarisation and categorisation |
