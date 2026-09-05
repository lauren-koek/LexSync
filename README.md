# LexSync

Singapore regulatory monitoring pipeline. Scrapes MAS regulations and guidance, extracts text via OCR, runs LLM analysis, and stores results in PostgreSQL.

## Structure

| Path | Purpose |
|---|---|
| `scraper/src/mas_regulations_scraper.py` | Playwright scraper — produces JSON list of documents |
| `scraper/src/pdf_ocr.py` | PDF text extraction (pdfplumber + Tesseract fallback) |
| `db/` | SQLAlchemy 2.x models and session factory |
| `llm/processor.py` | Per-document LLM summarise/categorise via OpenRouter |
| `pipeline.py` | End-to-end orchestrator CLI |
| `Dockerfile` | Container image for the pipeline service |
| `docker-compose.yml` | PostgreSQL 16 + pipeline service |
| `requirements.txt` | Python dependencies |

## Quick Start with Docker

```bash
cp .env.example .env   # fill in OPENROUTER_API_KEY
docker-compose up
```

The pipeline service waits for Postgres to be healthy before starting.

## Running locally

```bash
pip install -r requirements.txt

# start only Postgres
docker-compose up postgres -d

# run the scraper first (produces scraper/output/mas_regulations_and_guidance.json)
python -m scraper.src.mas_regulations_scraper

# run the pipeline
python pipeline.py
```

See `docs/pipeline.md` for stage-by-stage usage and `docs/database.md` for schema and DB management.
