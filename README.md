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

## Legal Resilience Engine demo

Detects which internal legal assets (playbooks, template clauses, SOPs) are
affected by a regulatory change, explains *why* with statutory citations, and
simulates propagating the fix — a structural answer to "how do we build
compliance tools resilient to regulatory change, not just reactive to it?"

## Pipeline

```
ingest.py  →  store.py  →  analyse.py  →  notify.py
(chunk)       (embed +      (LLM impact    (dashboard +
              match)         analysis)      propagate)
```

Each stage reads the previous stage's JSON output and writes its own:

| Script | Reads | Writes |
|---|---|---|
| `ingest.py` | files in `sample_docs/` (or hardcoded samples) | `ingested_data.json` |
| `store.py` | `ingested_data.json` | `matched_pairs.json` |
| `analyse.py` | `matched_pairs.json` | `impact_report.json` |
| `notify.py` | `impact_report.json` | `updated_playbook.md` (+ terminal dashboard) |

`run_pipeline.py` runs all four in sequence. `app.py` is a Streamlit UI over
the same functions, for the live demo.

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

Without an API key, `analyse.py` automatically uses a deterministic
rule-based fallback so the pipeline always runs end-to-end.

## Running it

**CLI (for a recorded video / terminal demo):**
```bash
python run_pipeline.py
```

**Browser (for live judging):**
```bash
streamlit run app.py
```
Then open http://localhost:8501, paste/upload a regulation and an internal
asset in the sidebar, and click **Run Resilience Analysis**.

## Demo script (suggested, ~90 seconds)

1. Open the Streamlit app with the pre-filled PDPA sample data already in
   the text boxes.
2. Click **Run Resilience Analysis** — narrate: "the engine just chunked
   both documents, embedded them, and found which internal clauses are
   semantically related to this regulatory change."
3. Point at the **Impact Summary** table — two clauses flagged AFFECTED
   with impact score 7/10, two correctly *not* flagged.
4. Expand an affected clause — show the **redline diff** (old retention
   period struck through in red, new one in green) and the **statutory
   citation + reasoning**.
5. Scroll to **updated_playbook.md** — "this is the propagation step: the
   fix is already written into the playbook and an email notification was
   dispatched (dry-run) to the clause owner."
6. Close by reframing: this isn't a horizon-scanning alert feed — it answers
   the three things the problem statement asks for: *which* assets are
   affected, *how*, and it *propagates* the fix before the stale version is
   relied on.

## Extending beyond the hackathon

- Swap `sample_docs/` hardcoded text for a real scraper (Component 1 in the
  original prototype notes) that diffs government gazette/regulator pages.
- Qdrant is in-memory; point `QdrantClient` at a persistent instance to keep
  a durable, growing knowledge base across regulatory updates over time.
- `dispatch_updates(dry_run=True)` in `notify.py` is a documented extension
  point for real SMTP delivery — do not hardcode credentials, read them from
  environment variables.
