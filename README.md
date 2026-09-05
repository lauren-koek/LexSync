# LexSync

LexSync monitors Singapore regulatory updates and helps legal and compliance
teams identify internal documents that may need to change. It combines a React
web interface, a FastAPI backend, PostgreSQL with pgvector, private object
storage, local embeddings, and optional OpenRouter analysis.

This guide is written for someone running LexSync for the first time. Start
with [Running LexSync locally](#running-lexsync-locally). The FAQ explains
[Railway deployment](#how-do-we-deploy-lexsync-to-railway),
[blob storage](#how-does-blob-storage-work), and the
[full architecture](#what-is-the-full-software-architecture).

## Repository guide

| Path | Purpose |
|---|---|
| `frontend/` | React 18 and Vite web interface |
| `backend/main.py` | Production FastAPI entry point, database startup, CORS, and frontend hosting |
| `backend/api/` | HTTP routes and request/response schemas |
| `backend/analysis/` | Document ingestion, semantic matching, impact analysis, and suggestions |
| `backend/storage/` | Private S3-compatible storage for original internal PDFs |
| `backend/scraper/` | MAS website scraper, PDF download, and OCR |
| `backend/db/` | SQLAlchemy models, PostgreSQL sessions, and migrations |
| `backend/llm/` | OpenRouter client, prompts, and document processing |
| `backend/pipeline.py` | One complete regulatory-processing run |
| `Dockerfile` | Production image: builds React, installs Python/OCR tools, and runs FastAPI |
| `docker-compose.yml` | Local pgvector/PostgreSQL only |
| `railway.toml` | Railway build, web start command, health check, and restart policy |
| `entrypoint.sh` | Optional always-running scheduled-pipeline worker |

## Running LexSync locally

### What needs to be installed?

- [Git](https://git-scm.com/downloads).
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) for the
  local database.
- Python 3.14. The `Makefile` uses `python3.14` by default.
- Node.js and npm. Node 22 is safest because it matches production.
- An OpenRouter key for live AI analysis. Direct analysis has an offline
  fallback, and the regulatory pipeline can use `--skip-llm` without a key.
- S3-compatible credentials only if PDF upload and retention are needed. A
  Railway Bucket can be used from local development.

Run the following commands from the repository root (the folder containing
this README).

### Step 1: create the local settings file

```bash
cp .env.example .env
```

Open `.env` in a text editor. For the standard local setup, change the database
port to **5433** because Docker maps container port 5432 to host port 5433:

```dotenv
DATABASE_URL=postgresql://lexsync:lexsync@localhost:5433/lexsync
OPENROUTER_API_KEY=replace_with_a_real_key_if_available
OPENROUTER_MODEL=deepseek/deepseek-v4-flash-0731
FRONTEND_ORIGINS=http://localhost:5173
VITE_API_BASE_URL=http://localhost:8000
```

Do not commit `.env`; it contains secrets. With no OpenRouter key, leave the
value blank and use `--skip-llm` for regulatory pipeline runs.

### Step 2: start PostgreSQL

```bash
docker compose up -d postgres
docker compose ps
```

The `postgres` row should eventually say `healthy`. This starts
`pgvector/pgvector:pg16` and persists data in the Docker volume
`postgres_data`. It does **not** start the API, frontend, or pipeline.

### Step 3: start the backend

```bash
make dev
```

The first run creates `.venv`, installs Python dependencies, creates the
pgvector extension and tables, applies migrations, and starts FastAPI with
automatic reload. Keep this Terminal window open.

Check these links:

- Health: <http://localhost:8000/api/v1/health>
- Interactive API documentation: <http://localhost:8000/docs>

The health response should be:

```json
{"status":"ok","service":"lexsync-backend"}
```

### Step 4: start the frontend

Open a second Terminal window and run:

```bash
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. Vite sends browser requests beginning with
`/api` to FastAPI at `http://localhost:8000`.

### Step 5: optionally configure PDF storage

PDF upload requires all five values. Copy credentials from a Railway Bucket or
another S3-compatible provider into `.env`:

```dotenv
AWS_ENDPOINT_URL=https://storage.railway.app
S3_BUCKET_NAME=the_actual_bucket_name
AWS_DEFAULT_REGION=auto
AWS_ACCESS_KEY_ID=the_access_key
AWS_SECRET_ACCESS_KEY=the_secret_key
```

Restart `make dev` after changing `.env`. The rest of LexSync runs without
these variables, but internal-document upload, viewing, and deletion return a
storage-configuration error.

### Step 6: optionally run a regulatory update

The web app and pipeline are separate processes. Run one pipeline pass with:

```bash
python -m backend.pipeline --limit 5
```

Without an OpenRouter key:

```bash
python -m backend.pipeline --limit 5 --skip-llm
```

The default input is
`backend/scraper/output/mas_regulations_and_guidance.json`. Create it first if
needed:

```bash
python backend/scraper/src/mas_regulations_scraper.py --days 7 --download-pdfs
```

See [backend/docs/pipeline.md](backend/docs/pipeline.md) for all stages and
flags.

### Step 7: run the tests

```bash
make test
```

Run the frontend tests separately:

```bash
cd frontend
npm test -- --run
```

### How do we stop or reset the local setup?

Stop the frontend and backend with `Ctrl+C`, then stop PostgreSQL:

```bash
docker compose down
```

This preserves database data. `docker compose down --volumes` deliberately
deletes the local database and cannot recover its records.

## Frequently asked questions

### Is there a simpler, production-like local option?

Yes. The Dockerfile builds React and FastAPI into one image, like Railway.
PostgreSQL still runs separately.

```bash
docker compose up -d postgres
docker build -t lexsync-local .
docker run --rm -p 8000:8000 \
  --env-file .env \
  -e DATABASE_URL=postgresql://lexsync:lexsync@host.docker.internal:5433/lexsync \
  lexsync-local
```

Open <http://localhost:8000>. FastAPI serves both the compiled React app and
`/api/v1/*`, so no Vite server is needed. `host.docker.internal` lets this
container reach the host database; Linux may need an additional host-gateway
Docker setting.

### How do we deploy LexSync to Railway?

The recommended Railway project has four resources:

1. **LexSync Web** — public service built from this repository.
2. **Postgres** — private database used by both application services.
3. **Documents** — private Railway Bucket for original PDFs.
4. **LexSync Pipeline** — recommended private worker for scheduled regulatory
   updates. `railway.toml` does not create it automatically; add a second
   service from the same repository.

#### A. Create the project and database

1. Push the repository to GitHub and create an empty Railway project.
2. Select **New → Database → PostgreSQL** and name it `Postgres`.
3. Confirm that the database supports the `vector` extension. LexSync runs
   `CREATE EXTENSION IF NOT EXISTS vector` at startup and cannot create its
   vector columns if the extension is unavailable.

Railway exposes `DATABASE_URL` on the database. Use a reference variable so
credential changes stay synchronized; do not copy the URL manually.

#### B. Create the web service

1. Select **New → GitHub Repo**, choose this repository, and name the service
   `LexSync Web`.
2. Railway detects the root `Dockerfile`. It compiles React and installs
   Python, Tesseract, Poppler, Playwright Chromium, and the backend.
3. In **Variables**, add the values below. Names inside `${{...}}` must exactly
   match the resource names on the Railway canvas.

```dotenv
DATABASE_URL=${{Postgres.DATABASE_URL}}
OPENROUTER_API_KEY=replace_with_the_real_secret
OPENROUTER_MODEL=deepseek/deepseek-v4-flash-0731
AWS_ENDPOINT_URL=${{Documents.ENDPOINT}}
S3_BUCKET_NAME=${{Documents.BUCKET}}
AWS_DEFAULT_REGION=${{Documents.REGION}}
AWS_ACCESS_KEY_ID=${{Documents.ACCESS_KEY_ID}}
AWS_SECRET_ACCESS_KEY=${{Documents.SECRET_ACCESS_KEY}}
```

4. Under **Settings → Networking**, generate a public domain.
5. Deploy the staged changes.
6. Visit `https://YOUR-DOMAIN/api/v1/health`, then the domain itself.

`railway.toml` builds the Dockerfile, starts Uvicorn on Railway's `$PORT`,
checks `/api/v1/health`, retries a failed process up to three times, and allows
100 seconds for the health check. React and the API are one public deployment,
not two services.

Tables and idempotent migrations run whenever the web process starts. If its
first deployment races the new database and fails, wait for Postgres to become
healthy and redeploy the web service.

#### C. Create and connect the private bucket

1. Select **New → Bucket**, choose a region, and name it `Documents`.
2. Open its **Credentials** tab. Railway Buckets are private and S3-compatible;
   the application does not make this bucket public.
3. Add the five bucket reference variables above to the web service.
4. Add the same references to the pipeline worker.
5. Deploy the staged variable changes.

Railway calls its bucket-name variable `BUCKET`, while LexSync expects
`S3_BUCKET_NAME`; the reference maps between those names. Older buckets may
require path-style URLs, while the current storage client explicitly uses
virtual-hosted addressing. Check the bucket Credentials tab if an older bucket
cannot connect.

Official references: [Dockerfile deployments](https://docs.railway.com/builds/dockerfiles),
[variable references](https://docs.railway.com/variables/reference), and
[Storage Buckets](https://docs.railway.com/storage-buckets).

#### D. Add the recommended scheduled-pipeline worker

The checked-in Railway configuration starts only the web process. To automate
regulatory monitoring:

1. Add this GitHub repository to the Railway project a second time.
2. Name the service `LexSync Pipeline` and do not create a public domain.
3. Add the same database, OpenRouter, and bucket variables as the web service.
4. Override the worker's start command with:

```bash
/app/entrypoint.sh
```

5. Optionally add:

```dotenv
PIPELINE_INTERVAL_HOURS=24
SCRAPER_DAYS=7
```

6. Deploy and look for `PostgreSQL is ready`, `Starting pipeline run`, and
   `Run complete` in its logs.

`entrypoint.sh` waits for PostgreSQL, creates tables, applies migrations, runs
the MAS scraper and pipeline, waits for the selected interval, then repeats.
It is an **always-running worker**, so it consumes compute while waiting.

Do not enable Railway's **Cron Schedule** while this worker uses
`entrypoint.sh`. Railway cron processes must finish and exit, but this script
contains an infinite scheduling loop. A future cost-saving change could add a
one-shot script and schedule it in Railway Cron (which runs in UTC); that is
not the current setup. See [Railway Cron Jobs](https://docs.railway.com/cron-jobs).

### How does blob storage work?

“Blob storage” means S3-compatible object storage for original PDF bytes.
Railway calls this a **Storage Bucket**.

When a user uploads an internal PDF:

1. The browser sends it to `POST /api/v1/internal-documents`.
2. FastAPI reads at most 10 MB plus one validation byte.
3. The backend checks its `.pdf` name, `application/pdf` content type, `%PDF-`
   signature, size, and extractable text.
4. A SHA-256 digest detects exact duplicate uploads.
5. The text is split into legal clauses and embedded locally with
   `BAAI/bge-small-en-v1.5` through FastEmbed.
6. Original bytes go to
   `internal-documents/<document UUID>/<safe filename>` in the private bucket.
7. Metadata, clause text, and 384-dimensional vectors go to PostgreSQL. Large
   PDF bytes do not.
8. If the database write fails after upload, the backend attempts to remove
   the new bucket object so it does not become orphaned.

For viewing, the API creates a presigned GET URL valid for 900 seconds (15
minutes). The bucket remains private and the browser gets temporary access to
one object. Deletion removes the bucket object and database record; database
cascade rules remove related chunks and suggestions.

The bucket is durable storage. A Railway service's local filesystem is not:
deployments can replace containers and erase local files. Never expose bucket
credentials to React or put them in a `VITE_` variable, because Vite variables
can be included in browser code.

### What is the full software architecture?

```mermaid
flowchart TB
    User[Legal or compliance user] -->|HTTPS| Web

    subgraph Browser[User browser]
        Web[React 18 single-page application]
        ApiClient[frontend/src/api.js]
        Web --> ApiClient
    end

    subgraph Railway[Railway project / production]
        subgraph WebService[LexSync Web - public]
            Static[FastAPI StaticFiles<br/>compiled Vite assets]
            API[FastAPI /api/v1 routes]
            Startup[Startup lifecycle<br/>tables and migrations]
            Analysis[Request-local analysis]
            InternalDocs[Internal document ingestion]
            Suggestions[Suggestions and reanalysis]
            Updates[Regulatory update queries]
            Static --> API
            API --> Analysis
            API --> InternalDocs
            API --> Suggestions
            API --> Updates
            Startup --> DB
        end

        subgraph WorkerService[LexSync Pipeline - private, recommended]
            Loop[entrypoint.sh interval loop]
            Scraper[MAS scraper<br/>Playwright and BeautifulSoup]
            OCR[PDF extraction and OCR<br/>pdfplumber and Tesseract]
            Pipeline[backend.pipeline<br/>processing and upsert]
            Loop --> Scraper --> OCR --> Pipeline
        end

        DB[(PostgreSQL 16 and pgvector<br/>documents, chunks, vectors,<br/>suggestions, migration state)]
        Bucket[(Private Railway Bucket<br/>original internal PDFs)]
    end

    ApiClient -->|same-origin /api/v1| API
    InternalDocs -->|put or delete PDF| Bucket
    API -->|15-minute presigned URL| ApiClient
    InternalDocs -->|metadata, clauses, vectors| DB
    Suggestions <-->|cosine search and results| DB
    Updates --> DB
    Pipeline --> DB
    Pipeline --> Suggestions

    FastEmbed[FastEmbed on application CPU<br/>BAAI/bge-small-en-v1.5<br/>384 dimensions]
    OpenRouter[OpenRouter chat completion API]
    MAS[MAS website and regulatory PDFs]
    SSO[Singapore Statutes Online]

    InternalDocs -->|create embeddings| FastEmbed
    Analysis -->|in-memory similarity| FastEmbed
    Suggestions -->|embed search text| FastEmbed
    Analysis -. optional live analysis .-> OpenRouter
    Pipeline -. optional summaries and categories .-> OpenRouter
    Suggestions -. optional impact analysis .-> OpenRouter
    Scraper --> MAS
    Scraper --> SSO
```

The two main paths are:

- **Interactive:** React calls FastAPI, which reads or writes PostgreSQL and
  the private bucket. Direct analysis is request-local and can use a
  deterministic offline fallback without OpenRouter.
- **Monitoring:** the worker periodically scrapes MAS, extracts regulatory
  PDFs, optionally asks OpenRouter for summaries, upserts regulations, searches
  the persistent internal vectors, and saves proposed changes. A suggestion
  failure is logged without rolling back successful regulatory ingestion.

### Which environment variables are required?

| Variable | Required when | Meaning |
|---|---|---|
| `DATABASE_URL` | Always | PostgreSQL URL; the database must support pgvector |
| `OPENROUTER_API_KEY` | Live LLM analysis or pipeline without `--skip-llm` | Secret OpenRouter credential |
| `OPENROUTER_MODEL` | Optional | Defaults to `deepseek/deepseek-v4-flash-0731` |
| `FRONTEND_ORIGINS` | Separate frontend origin | Comma-separated CORS allow-list |
| `VITE_API_BASE_URL` | Local Vite development | Backend target for Vite's `/api` proxy |
| `AWS_ENDPOINT_URL` | Internal PDF storage | Base S3-compatible endpoint |
| `S3_BUCKET_NAME` | Internal PDF storage | Actual bucket name |
| `AWS_DEFAULT_REGION` | Internal PDF storage | Bucket region; Railway commonly supplies `auto` |
| `AWS_ACCESS_KEY_ID` | Internal PDF storage | Secret S3 access-key ID |
| `AWS_SECRET_ACCESS_KEY` | Internal PDF storage | Secret S3 access key |
| `PIPELINE_INTERVAL_HOURS` | Optional worker | Hours between runs; default `24` |
| `SCRAPER_DAYS` | Optional worker | Recent days scraped; default `7` |
| `PORT` | Supplied by Railway | Uvicorn port; do not hardcode it on Railway |

### What API endpoints are available?

- `GET /api/v1/health` — deployment health.
- `POST /api/v1/analysis` — analyze pasted regulation and internal text.
- `POST /api/v1/analysis/upload` — analyze temporary TXT/PDF uploads without
  adding them to the shared internal library.
- `POST /api/v1/updates` and `GET /api/v1/documents` — regulatory data.
- `POST /api/v1/internal-documents` — store, chunk, embed, and index a PDF.
- `GET /api/v1/internal-documents` — list or title-search the library.
- `POST /api/v1/internal-documents/search` — semantic pgvector search.
- `GET /api/v1/internal-documents/{id}` — chunks and suggestions.
- `GET /api/v1/internal-documents/{id}/pdf-url` — temporary private PDF URL.
- `DELETE /api/v1/internal-documents/{id}` — remove PDF and database record.
- `POST /api/v1/internal-documents/{id}/reanalyze` — regenerate suggestions.
- `GET /api/v1/documents/{id}/suggestions` — regulation suggestions.
- `PATCH /api/v1/document-suggestions/{id}` — change review status.

Interactive schemas and request forms are at `/docs` while the API is running.

### Why will an internal PDF not upload?

- **Missing object-storage configuration:** add all five S3 variables and
  restart or redeploy.
- **503 storage error:** compare endpoint, credentials, bucket name, and URL
  style with the bucket's current Credentials tab.
- **413 / exceeds 10 MB:** reduce the PDF below the fixed limit.
- **422 / no extractable text:** library upload uses pdfplumber and rejects
  image-only scans, encryption, and malformed PDFs. OCR it into a text-bearing
  PDF before retrying.
- **200 instead of 201:** expected for an exact duplicate; SHA-256
  deduplication returns the existing document.

### Why can the frontend not reach the backend locally?

1. Confirm <http://localhost:8000/api/v1/health> works directly.
2. Open the frontend at <http://localhost:5173>, not as a local file.
3. Set `VITE_API_BASE_URL=http://localhost:8000` before starting Vite.
4. Include `http://localhost:5173` in `FRONTEND_ORIGINS`.
5. Restart both processes after changing `.env`.

Production uses one domain for React and the API, avoiding this two-origin
development arrangement.

### Why does database startup fail?

- Wait until `docker compose ps` reports Postgres as healthy.
- Use port 5433 from host-run Python. Use port 5432 only inside a Docker or
  Railway network where it is the database service port.
- Check that `DATABASE_URL` contains the correct credentials and database.
- An error mentioning `vector` means pgvector is missing or the database user
  cannot create the extension. The local compose image includes it.
- Inspect backend logs for migration errors. Migrations run in filename order
  at startup and are designed to be idempotent.

See [backend/docs/database.md](backend/docs/database.md) for schema details.

### Why is OpenRouter analysis unavailable or failing?

- Set `OPENROUTER_API_KEY` on the process running FastAPI or the pipeline, then
  restart it.
- Confirm the account can use `OPENROUTER_MODEL` and has credit.
- Direct analysis can use the offline heuristic and labels its source
  `offline_heuristic`.
- The regulatory pipeline needs `--skip-llm` without a key.
- OpenRouter requests have a 120-second timeout; inspect provider and Railway
  logs when large requests time out.

### Why does a Railway deployment fail?

- **Frontend build:** reproduce with `cd frontend && npm ci && npm run build`.
- **Python dependencies:** reproduce in fresh Python 3.14 with
  `pip install -r requirements.txt`.
- **Health check:** confirm Railway supplies `$PORT` and
  `/api/v1/health` is reachable; do not use a fixed production port.
- **Database startup:** confirm `DATABASE_URL` references the right healthy
  Postgres resource.
- **Worker restarts:** check `/app/entrypoint.sh`, its database reference, and
  the worker logs.
- **Only uploads fail:** check bucket references. Storage is separate from the
  web health check.

## Other entry points

Compatibility CLI:

```bash
python -m backend.run_pipeline
```

Older Streamlit interface:

```bash
streamlit run app.py
```

Then open <http://localhost:8501>. React/FastAPI is the primary deployment.

## Current operational limitations

- Authentication and workspace ownership are not implemented; the internal
  library is shared by everyone who can access the service.
- PDF ingestion and embedding are synchronous. The first FastEmbed model load
  can make a request noticeably slower.
- The worker is an always-running interval loop, not a one-shot Railway Cron
  job or queue.
- Real email delivery is not configured. `dispatch_updates(dry_run=True)` in
  `backend/analysis/notify.py` is the extension point; credentials must come
  from environment variables, never source code.
