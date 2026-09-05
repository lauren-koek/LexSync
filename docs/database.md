# Database

PostgreSQL 16. SQLAlchemy 2.x models in `db/models.py`. Tables are created automatically on first pipeline run via `create_tables()`.

## Schema — `documents` table

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | No | Primary key, auto-generated |
| `source_url` | text | No | Document page URL (unique) |
| `doc_type` | varchar(100) | Yes | e.g. `"Circular"`, `"Guidelines"` |
| `date` | date | Yes | Publication date parsed from scraper output |
| `title` | text | Yes | Document title |
| `topic` | text | Yes | Regulatory topic from MAS |
| `tags` | jsonb | Yes | Array of free-text tags |
| `applies_to` | jsonb | Yes | Array of entity types the document applies to |
| `related_items` | jsonb | Yes | Array of related document URLs |
| `pdf_url` | text | Yes | Direct PDF download URL |
| `pdf_local_path` | text | Yes | Local path of downloaded PDF (reserved, not yet populated) |
| `ocr_text` | text | Yes | Full extracted text from PDF |
| `llm_summary` | text | Yes | 80–150 word LLM-generated summary |
| `llm_categories` | jsonb | Yes | Array of category strings from the standard tag list |
| `llm_impact_check` | text | Yes | LLM-generated impact check block |
| `scraped_at` | timestamptz | Yes | Timestamp of last scrape |
| `processed_at` | timestamptz | Yes | Timestamp of last LLM processing |
| `created_at` | timestamptz | No | Row creation time (server default) |
| `updated_at` | timestamptz | Yes | Row last-update time (auto on update) |

`source_url` carries a unique constraint — pipeline runs upsert on it.

## Running locally with Docker

Start only Postgres:

```bash
docker-compose up postgres -d
```

Then run the pipeline (tables are created automatically):

```bash
DATABASE_URL=postgresql://lexsync:lexsync@localhost:5432/lexsync python pipeline.py
```

Or put `DATABASE_URL` in `.env` and omit the prefix.

## Connecting to the DB

```bash
psql postgresql://lexsync:lexsync@localhost:5432/lexsync
```

`DATABASE_URL` format:

```
postgresql://<user>:<password>@<host>:<port>/<dbname>
```

Default credentials from `docker-compose.yml`: user `lexsync`, password `lexsync`, db `lexsync`.

## Resetting / recreating tables

Drop and recreate from a psql session:

```sql
DROP TABLE documents;
```

Then re-run the pipeline — `create_tables()` will recreate the schema.

To reset via Python:

```python
from db.models import Base
from db.session import engine

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
```
