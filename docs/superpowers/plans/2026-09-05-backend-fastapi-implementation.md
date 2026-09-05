# Backend Package and FastAPI API Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Move LexSync's existing backend and branch analysis code under backend/, expose analysis through FastAPI, and run the API beside the existing Dockerized scheduled pipeline.

**Architecture:** backend/ is the only Python backend package. backend/analysis contains the branch legal resilience workflow, while backend/db, backend/llm, and backend/scraper contain the existing main tools it uses. backend/main.py owns the FastAPI app and delegates to a service layer; app.py remains a development-only Streamlit client.

**Tech Stack:** Python 3.14, FastAPI, Uvicorn, Pydantic, Qdrant/FastEmbed, existing SQLAlchemy/PostgreSQL and OpenRouter integrations, pytest, Docker Compose.

**Spec:** docs/superpowers/specs/2026-09-05-backend-fastapi-design.md

## Global Constraints

- Preserve the existing scraper, PDF OCR, database, and LLM implementations from main; update imports and paths only where the package move requires it.
- API analysis is request-local and must not write ingested_data.json, matched_pairs.json, impact_report.json, or updated_playbook.md.
- Keep the existing scheduled pipeline as a separate Docker Compose service using entrypoint.sh.
- Required API endpoints are GET /api/v1/health and POST /api/v1/analysis.
- Required request fields are non-empty regulation_text and internal_asset_text; IDs default to Uploaded_Regulation and Uploaded_Internal_Asset.
- CORS origins come from FRONTEND_ORIGINS, defaulting to http://localhost:3000.
- Run focused tests after each behavior change and run the full verification suite before completion.

---

### Task 1: Add failing API contract tests

**Files:**
- Create: tests/api/test_health.py
- Create: tests/api/test_analysis.py
- Create: tests/conftest.py

**Interfaces:**
- Consumes: the not-yet-created backend.main:app FastAPI application.
- Produces: executable checks for health, validation, response serialization, and API file isolation.

- [ ] Step 1: Write the failing health test.

~~~python
from fastapi.testclient import TestClient

from backend.main import app


def test_health_returns_backend_status():
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "lexsync-backend"}
~~~

- [ ] Step 2: Write failing validation tests.

~~~python
from fastapi.testclient import TestClient

from backend.main import app


def test_analysis_rejects_missing_regulation_text():
    response = TestClient(app).post(
        "/api/v1/analysis",
        json={"internal_asset_text": "Clause 8. Keep logs."},
    )

    assert response.status_code == 422


def test_analysis_rejects_whitespace_only_asset_text():
    response = TestClient(app).post(
        "/api/v1/analysis",
        json={"regulation_text": "Section 12A.", "internal_asset_text": "   "},
    )

    assert response.status_code == 422
~~~

- [ ] Step 3: Write a response contract test with a deterministic service result.

~~~python
import backend.api.routes as routes
from fastapi.testclient import TestClient


def test_analysis_returns_frontend_contract(monkeypatch):
    monkeypatch.setattr(
        routes,
        "run_analysis",
        lambda **kwargs: {
            "regulation_id": kwargs["regulation_id"],
            "asset_id": kwargs["asset_id"],
            "clause_count": 2,
            "match_count": 1,
            "report": [{
                "regulation": {"content": "Section 12A."},
                "asset": {"content": "Clause 8."},
                "similarity_score": 0.81,
                "analysis": {
                    "is_affected": True,
                    "impact_score": 7,
                    "legal_reasoning": "A retention period changed.",
                    "proposed_amended_clause": "Retain for seven years.",
                    "statutory_citations": ["Section 12A"],
                },
                "redline_diff": "[-three years-] {+seven years+}",
                "analysis_source": "offline_heuristic",
            }],
            "propagation": {
                "dispatched": 1,
                "dry_run": True,
                "timestamp": "2026-09-05T00:00:00+00:00",
            },
        },
    )

    response = TestClient(routes.app).post(
        "/api/v1/analysis",
        json={
            "regulation_text": "Section 12A.",
            "internal_asset_text": "Clause 8.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["regulation_id"] == "Uploaded_Regulation"
    assert body["asset_id"] == "Uploaded_Internal_Asset"
    assert body["report"][0]["analysis"]["impact_score"] == 7
~~~

- [ ] Step 4: Write the API isolation test.

~~~python
def test_analysis_does_not_write_shared_artifacts(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(routes, "run_analysis", lambda **kwargs: {
        "regulation_id": "Uploaded_Regulation",
        "asset_id": "Uploaded_Internal_Asset",
        "clause_count": 0,
        "match_count": 0,
        "report": [],
        "propagation": {
            "dispatched": 0,
            "dry_run": True,
            "timestamp": "2026-09-05T00:00:00+00:00",
        },
    })

    response = TestClient(routes.app).post(
        "/api/v1/analysis",
        json={"regulation_text": "Section 1.", "internal_asset_text": "Clause 1."},
    )

    assert response.status_code == 200
    assert list(tmp_path.iterdir()) == []
~~~

- [ ] Step 5: Run the new tests and verify they fail because the API package does not exist.

Run: pytest tests/api -q

Expected: collection fails with ModuleNotFoundError for backend.main.

---

### Task 2: Move the existing backend code into backend/

**Files:**
- Create: backend/__init__.py and backend/analysis/__init__.py
- Move: ingest.py, store.py, analyse.py, and notify.py into backend/analysis/
- Move: db/ into backend/db/
- Move: llm/ into backend/llm/
- Move: scraper/ into backend/scraper/
- Move: pipeline.py and run_pipeline.py into backend/
- Modify: imports in moved modules and app.py

**Interfaces:**
- Consumes: the current main source modules and branch analysis modules.
- Produces: importable modules under backend.* with no backend implementation remaining at the repository root.

- [ ] Step 1: Move the source files.

Run:

~~~bash
mkdir -p backend/analysis backend/db backend/llm/prompts backend/scraper/src
mv ingest.py store.py analyse.py notify.py backend/analysis/
mv db/__init__.py db/models.py db/session.py backend/db/
mv llm/__init__.py llm/client.py llm/processor.py backend/llm/
mv llm/prompts/__init__.py llm/prompts/newsletter_prompt.py backend/llm/prompts/
mv scraper/README.md scraper/src/pdf_ocr.py backend/scraper/
mv pipeline.py run_pipeline.py backend/
rmdir db llm/prompts llm scraper/src scraper
~~~

- [ ] Step 2: Update imports to the new package paths.

Use these exact relationships:

~~~python
# backend/pipeline.py
from backend.db import Document, create_tables, get_session
from backend.llm.processor import process_document
from backend.scraper.src.pdf_ocr import download_and_ocr

# backend/llm/processor.py
from backend.llm.client import chat
from backend.llm.prompts.newsletter_prompt import PROMPT

# backend/db/__init__.py
from backend.db.models import Document
from backend.db.session import SessionLocal, create_tables, get_session
~~~

Update backend/run_pipeline.py to import backend.analysis.ingest, backend.analysis.store, backend.analysis.analyse, and backend.analysis.notify. Update app.py to import those same package paths.

- [ ] Step 3: Update execution commands.

Use python -m backend.run_pipeline for the demo CLI and python -m backend.pipeline for the production pipeline. Preserve root-relative generated artifact paths because Docker and local commands use the repository root as the working directory.

- [ ] Step 4: Run the import smoke checks.

Run:

~~~bash
python -c "import backend.analysis.ingest, backend.analysis.store, backend.analysis.analyse, backend.analysis.notify"
python -c "import backend.pipeline"
~~~

Expected: the analysis import exits 0. The pipeline import exits 0 when DATABASE_URL is configured; otherwise it reports the existing database configuration error.

---

### Task 3: Add the in-memory analysis service

**Files:**
- Create: backend/analysis/service.py
- Modify: backend/analysis/store.py
- Modify: backend/analysis/notify.py
- Create: tests/analysis/test_service.py

**Interfaces:**
- Consumes: chunk_legal_document, build_index, find_impacted_assets, analyze_clause_impact, and generate_redline_diff.
- Produces: run_analysis(regulation_text, internal_asset_text, regulation_id, asset_id) returning the documented analysis response dictionary.

- [ ] Step 1: Write the failing service test.

~~~python
from backend.analysis import service


def test_run_analysis_builds_report_without_writing_artifacts(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    chunks = [
        {
            "id": "reg-1", "doc_id": "Reg", "source_type": "REGULATION",
            "title": "Reg — Section 1", "clause_reference": "Section 1",
            "content": "Section 1. Retain seven years.",
        },
        {
            "id": "asset-1", "doc_id": "Asset", "source_type": "INTERNAL_ASSET",
            "title": "Asset — Clause 1", "clause_reference": "Clause 1",
            "content": "Clause 1. Retain three years.",
        },
    ]
    monkeypatch.setattr(
        service.ingest,
        "chunk_legal_document",
        lambda text, source_type, doc_id: [
            chunk for chunk in chunks if chunk["source_type"] == source_type
        ],
    )
    monkeypatch.setattr(service.store, "build_index", lambda chunks, client=None: object())
    monkeypatch.setattr(
        service.store,
        "find_impacted_assets",
        lambda text, client=None: [{**chunks[1], "similarity_score": 0.8}],
    )
    monkeypatch.setattr(
        service.analyse,
        "analyze_clause_impact",
        lambda regulation, asset: service.analyse.LegalImpactAnalysis(
            is_affected=True,
            impact_score=7,
            legal_reasoning="Changed duration.",
            proposed_amended_clause="Clause 1. Retain seven years.",
            statutory_citations=["Section 1"],
        ),
    )

    result = service.run_analysis("regulation", "asset", "Reg", "Asset")

    assert result["clause_count"] == 2
    assert result["match_count"] == 1
    assert result["report"][0]["analysis"]["impact_score"] == 7
    assert list(tmp_path.iterdir()) == []
~~~

- [ ] Step 2: Run the service test and verify the missing service failure.

Run: pytest tests/analysis/test_service.py -q

Expected: FAIL because backend.analysis.service does not yet define run_analysis.

- [ ] Step 3: Add request-local vector-index support.

Change build_index to accept an optional QdrantClient and use that client when supplied. Change find_impacted_assets to accept the same optional client and query it. Preserve the current global-client defaults so the file-backed CLI behavior remains unchanged.

- [ ] Step 4: Implement the minimal orchestration.

The service must:
1. Chunk regulation_text as REGULATION and internal_asset_text as INTERNAL_ASSET.
2. Create a fresh in-memory QdrantClient for the request.
3. Build the index and query only internal asset matches for every regulation chunk.
4. Analyze each match with the existing offline-or-LLM function.
5. Generate the existing redline format.
6. Return regulation_id, asset_id, clause_count, match_count, report, and notify.summarize_updates(report, dry_run=True).

- [ ] Step 5: Add a pure propagation summary.

Implement summarize_updates(report, dry_run=True) in backend/analysis/notify.py. It returns dispatched, dry_run, and an ISO UTC timestamp without writing updated_playbook.md or sending email. Run pytest tests/analysis/test_service.py -q and verify PASS.

---

### Task 4: Add FastAPI schemas, routes, and application configuration

**Files:**
- Create: backend/api/__init__.py
- Create: backend/api/schemas.py
- Create: backend/api/routes.py
- Create: backend/main.py
- Modify: requirements.txt
- Modify: tests/api/test_analysis.py

**Interfaces:**
- Consumes: backend.analysis.service.run_analysis.
- Produces: backend.main:app, GET /api/v1/health, and POST /api/v1/analysis.

- [ ] Step 1: Add dependencies.

Append these entries to requirements.txt:

~~~text
fastapi
uvicorn[standard]
pytest
httpx
~~~

- [ ] Step 2: Implement request validation.

Use Pydantic v2 models with these fields and constraints:

~~~python
class AnalysisRequest(BaseModel):
    regulation_text: str = Field(min_length=1)
    internal_asset_text: str = Field(min_length=1)
    regulation_id: str = "Uploaded_Regulation"
    asset_id: str = "Uploaded_Internal_Asset"

    @field_validator("regulation_text", "internal_asset_text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value
~~~

Define response models for health, propagation, each report entry, and the complete analysis response. Use dict[str, Any] for regulation and asset payloads to preserve the current report shape.

- [ ] Step 3: Implement the routes.

Use an APIRouter with prefix /api/v1. The health route returns status ok and service lexsync-backend. The analysis route passes request.model_dump() to service.run_analysis and returns the result through the response model.

- [ ] Step 4: Implement backend/main.py.

Create the FastAPI app with title LexSync Backend and version 1.0.0. Add CORSMiddleware using a helper that splits FRONTEND_ORIGINS on commas and defaults to http://localhost:3000. Include the API router.

- [ ] Step 5: Run the API tests.

Run: pytest tests/api -q

Expected: all health, validation, response, and isolation tests PASS.

---

### Task 5: Update Docker and developer entry points

**Files:**
- Modify: Dockerfile
- Modify: docker-compose.yml
- Modify: entrypoint.sh
- Modify: app.py
- Modify: README.md
- Modify: docs/pipeline.md

**Interfaces:**
- Consumes: backend.main:app and backend.pipeline.
- Produces: api Docker Compose service on port 8000, the existing scheduled pipeline service, and documented local commands.

- [ ] Step 1: Make the Dockerfile default to FastAPI.

Use:

~~~dockerfile
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
~~~

- [ ] Step 2: Add an api Compose service.

The service uses the existing image build, waits for healthy Postgres, passes DATABASE_URL, OPENROUTER_API_KEY, OPENROUTER_MODEL, and FRONTEND_ORIGINS, and exposes 8000:8000. Keep the existing pipeline service and give it command ["/app/entrypoint.sh"] so it continues running the scheduler.

- [ ] Step 3: Update scheduler paths.

Change entrypoint.sh table setup to import backend.db.create_tables and change the processing command to python -m backend.pipeline. Update the scraper command to the moved backend.scraper module path when the existing scraper entry module is present.

- [ ] Step 4: Update the Streamlit development client and docs.

Change app.py imports to backend.analysis.ingest, backend.analysis.store, backend.analysis.analyse, and backend.analysis.notify. Document docker compose up --build, streamlit run app.py, and the future frontend URL http://localhost:8000/api/v1/analysis.

- [ ] Step 5: Validate Compose configuration.

Run docker compose config.

Expected: exit 0 with postgres, api, and pipeline services, API port 8000:8000, and pipeline command /app/entrypoint.sh.

---

### Task 6: Full verification and final review

**Files:**
- Modify: docs/superpowers/plans/2026-09-05-backend-fastapi-implementation.md to mark completed steps if using the plan as a live checklist.

**Interfaces:**
- Consumes: all implementation tasks above.
- Produces: a verified backend package, FastAPI app, Docker configuration, and clean tracked diff.

- [ ] Step 1: Run the complete test suite.

Run: pytest -q

Expected: exit 0 with no failures.

- [ ] Step 2: Run import and syntax verification.

Run:

~~~bash
python -m compileall -q backend app.py
python -c "from backend.main import app; print(sorted((route.path, sorted(route.methods or [])) for route in app.routes))"
~~~

Expected: compilation succeeds and the route list contains /api/v1/health and /api/v1/analysis.

- [ ] Step 3: Review repository state.

Run: git status --short && git diff --check

Expected: no conflict markers or whitespace errors; report any pre-existing untracked files separately from implementation changes.

