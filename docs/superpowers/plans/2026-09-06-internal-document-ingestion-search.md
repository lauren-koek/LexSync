# Internal Document Ingestion and Semantic Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shared PDF library that synchronously stores originals in AWS-compatible object storage, indexes extracted clauses in PostgreSQL/pgvector, supports semantic search and split-view reading, and persists automatic or manually regenerated regulatory-change suggestions.

**Architecture:** A focused ingestion service coordinates PDF validation, S3-compatible object storage, legal-aware chunking, embeddings, and atomic relational writes. The persistent pgvector index provides both document search and regulatory matching; a suggestion service owns idempotent analysis and review-state preservation. FastAPI exposes these capabilities to a React library/detail experience while the existing MAS pipeline invokes suggestion generation after saving OCR text.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2, PostgreSQL 16, pgvector, pdfplumber, boto3, pytest, React 18, Vite, Vitest, Testing Library, Tailwind CSS 4.

**Spec:** `docs/superpowers/specs/2026-09-06-internal-document-ingestion-search-design.md`

## Global Constraints

- Internal documents are shared globally; do not add authentication, owners, tenants, or permissions.
- Accept PDF uploads only, with the existing 10 MB maximum.
- Process uploads synchronously; do not add a queue or worker.
- Store originals using `AWS_ENDPOINT_URL`, `S3_BUCKET_NAME`, `AWS_DEFAULT_REGION`, `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY`.
- Keep embeddings at exactly 384 dimensions and query with pgvector cosine distance.
- Do not OCR image-only internal PDFs in this release.
- Preserve the existing request-local `/api/v1/analysis` workflow.
- Use test doubles for storage and embeddings; automated tests must not call S3 or hosted models.

---

### Task 1: Persistent Document and Suggestion Schema

**Files:**
- Modify: `backend/db/models.py`
- Modify: `backend/db/__init__.py`
- Create: `backend/db/migrations/0003_add_internal_documents_and_suggestions.py`
- Modify: `tests/db/test_migrations.py`
- Create: `tests/db/test_internal_document_models.py`

**Interfaces:**
- Produces: `InternalDocument`, `InternalDocumentChunk`, and `DocumentSuggestion` SQLAlchemy models.
- Produces: `SuggestionStatus` values `pending`, `accepted`, and `dismissed` stored as strings.
- Migration removes orphaned legacy chunk rows, creates the two parent/result tables, and changes chunks to reference `internal_documents.id`.

- [ ] **Step 1: Write failing model and migration-order tests**

```python
# tests/db/test_internal_document_models.py
from backend.db.models import DocumentSuggestion, InternalDocument, InternalDocumentChunk


def test_internal_chunk_belongs_to_parent_document():
    assert InternalDocumentChunk.__table__.c.internal_document_id.foreign_keys
    assert "doc_id" not in InternalDocumentChunk.__table__.c


def test_document_digest_and_suggestion_pair_are_unique():
    assert InternalDocument.__table__.c.sha256.unique is True
    constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in DocumentSuggestion.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert (
        "regulatory_document_id",
        "regulation_clause_reference",
        "internal_chunk_id",
    ) in constraint_columns
```

Extend `tests/db/test_migrations.py` so discovery includes `0003_third` and asserts it runs after `0002_second`.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest tests/db/test_internal_document_models.py tests/db/test_migrations.py -q`

Expected: model import/column assertions fail because the parent and suggestion models do not exist.

- [ ] **Step 3: Implement models, exports, and idempotent migration**

Add an `InternalDocument` model with the exact columns from the spec and relationships using `cascade="all, delete-orphan"`. Replace `InternalDocumentChunk.doc_id` with:

```python
internal_document_id: Mapped[UUID] = mapped_column(
    ForeignKey("internal_documents.id", ondelete="CASCADE"), nullable=False, index=True
)
document: Mapped["InternalDocument"] = relationship(back_populates="chunks")
```

Add `DocumentSuggestion` with JSON citations, string review status, both parent foreign keys, the chunk foreign key, analysis fields, and:

```python
UniqueConstraint(
    "regulatory_document_id",
    "regulation_clause_reference",
    "internal_chunk_id",
    name="uq_document_suggestion_match",
)
```

Migration `upgrade()` must execute explicit PostgreSQL `CREATE TABLE IF NOT EXISTS`, `DELETE FROM internal_document_chunks`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, and index/constraint statements in dependency order. Export all three models from `backend/db/__init__.py`.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `pytest tests/db/test_internal_document_models.py tests/db/test_migrations.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/db/models.py backend/db/__init__.py backend/db/migrations/0003_add_internal_documents_and_suggestions.py tests/db/test_internal_document_models.py tests/db/test_migrations.py
git commit -m "feat: model internal documents and suggestions"
```

---

### Task 2: AWS-Compatible Object Storage Boundary

**Files:**
- Create: `backend/storage/__init__.py`
- Create: `backend/storage/objects.py`
- Create: `tests/storage/test_objects.py`
- Modify: `requirements.txt`
- Modify: `.env.example`

**Interfaces:**
- Produces: `ObjectStorage.put(key: str, content: bytes, content_type: str) -> None`.
- Produces: `ObjectStorage.delete(key: str) -> None`, where a missing object succeeds.
- Produces: `ObjectStorage.presigned_get_url(key: str, expires_seconds: int = 900) -> str`.
- Produces: `get_object_storage() -> ObjectStorage`, cached from the five agreed environment variables.

- [ ] **Step 1: Write failing storage contract tests**

```python
# tests/storage/test_objects.py
from backend.storage.objects import S3ObjectStorage, StorageConfigurationError


def test_storage_uses_agreed_environment(monkeypatch):
    values = {
        "AWS_ENDPOINT_URL": "https://storage.example",
        "S3_BUCKET_NAME": "legal-docs",
        "AWS_DEFAULT_REGION": "auto",
        "AWS_ACCESS_KEY_ID": "key",
        "AWS_SECRET_ACCESS_KEY": "secret",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    captured = {}
    storage = S3ObjectStorage(client_factory=lambda **kwargs: captured.update(kwargs) or object())
    assert storage.bucket == "legal-docs"
    assert captured["endpoint_url"] == "https://storage.example"


def test_storage_rejects_missing_bucket(monkeypatch):
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    try:
        S3ObjectStorage(client_factory=lambda **kwargs: object())
    except StorageConfigurationError as exc:
        assert "S3_BUCKET_NAME" in str(exc)
    else:
        raise AssertionError("missing bucket must fail")
```

Add fake-client tests asserting `put_object`, `generate_presigned_url`, and `delete_object` receive the exact bucket and key, and that S3 `NoSuchKey` deletion is ignored.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest tests/storage/test_objects.py -q`

Expected: import failure because `backend.storage.objects` does not exist.

- [ ] **Step 3: Implement the adapter**

Define a `Protocol` for `ObjectStorage`, a `StorageConfigurationError`, and `S3ObjectStorage`. Construct boto3 with:

```python
boto3.client(
    "s3",
    endpoint_url=os.environ["AWS_ENDPOINT_URL"],
    region_name=os.environ["AWS_DEFAULT_REGION"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    config=Config(s3={"addressing_style": "virtual"}),
)
```

Map all provider exceptions to `ObjectStorageError` without including credentials. Add `boto3` to `requirements.txt` and document the five variables in `.env.example` without values.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `pytest tests/storage/test_objects.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/storage requirements.txt .env.example tests/storage/test_objects.py
git commit -m "feat: add S3-compatible document storage"
```

---

### Task 3: Synchronous PDF Ingestion Service

**Files:**
- Create: `backend/analysis/internal_documents.py`
- Modify: `backend/analysis/uploads.py`
- Modify: `internal_index.py`
- Create: `tests/analysis/test_internal_documents.py`
- Create: `tests/test_internal_index.py`

**Interfaces:**
- Produces: `ingest_pdf(filename: str, content_type: str, content: bytes, title: str | None, storage: ObjectStorage, session: Session, embed: Callable[[str], list[float]] = embed_text) -> IngestionResult`.
- Produces: `IngestionResult(document: InternalDocument, deduplicated: bool)`.
- Produces: `delete_internal_document(document_id: UUID, storage: ObjectStorage, session: Session) -> None`.
- Produces: `semantic_search(query: str, limit: int = 10, excerpts_per_document: int = 3, session: Session | None = None) -> list[dict]`.

- [ ] **Step 1: Write failing validation, success, deduplication, and compensation tests**

Use a real minimal PDF fixture created with `pypdf.PdfWriter` plus monkeypatched extraction text. The core assertions are:

```python
def test_ingest_pdf_uploads_and_saves_all_chunks(session, fake_storage, monkeypatch):
    monkeypatch.setattr(internal_documents, "extract_pdf_bytes", lambda _: "Clause 1. Keep records.\nClause 2. Report breaches.")
    result = internal_documents.ingest_pdf(
        "policy.pdf", "application/pdf", b"%PDF-1.4 test", "Policy",
        fake_storage, session, embed=lambda text: [0.0] * 384,
    )
    assert result.deduplicated is False
    assert result.document.chunk_count == 2
    assert fake_storage.puts[0][0].startswith(f"internal-documents/{result.document.id}/")


def test_duplicate_digest_does_not_upload_or_embed(session, fake_storage, monkeypatch):
    calls = []
    first = internal_documents.ingest_pdf(
        "a.pdf", "application/pdf", b"%PDF-same", None,
        fake_storage, session, embed=lambda text: calls.append(text) or [0.0] * 384,
    )
    second = internal_documents.ingest_pdf(
        "b.pdf", "application/pdf", b"%PDF-same", None,
        fake_storage, session, embed=lambda text: calls.append(text) or [0.0] * 384,
    )
    assert second.document.id == first.document.id
    assert second.deduplicated is True
    assert len(fake_storage.puts) == 1
```

Also test extension, MIME, 10 MB, bad signature, encrypted/unreadable, blank extraction, wrong embedding dimension, database flush failure deleting only the new object, and storage deletion occurring before database deletion.

- [ ] **Step 2: Run ingestion tests and verify RED**

Run: `pytest tests/analysis/test_internal_documents.py -q`

Expected: import failure because the service does not exist.

- [ ] **Step 3: Implement minimal ingestion and deletion**

Extract a bytes-based strict PDF helper in `uploads.py`; do not reuse the forgiving disk fallback in `ingest.py`. Sanitize filenames to a basename containing alphanumerics, spaces, dots, dashes, and underscores. Query SHA-256 before extraction. Build all chunk dictionaries, validate every embedding length, upload once, add parent and rows, and call `session.flush()` inside a `try/except` that deletes the exact new key before re-raising.

Update `internal_index.py` write/read payloads to use `internal_document_id` and parent title. Keep compatibility wrappers only where existing tests require them.

- [ ] **Step 4: Write and verify RED semantic-search tests**

```python
def test_semantic_search_groups_chunks_by_document(session, embedded_documents):
    results = semantic_search("breach reporting", limit=2, excerpts_per_document=2, session=session)
    assert [item["title"] for item in results] == ["Incident Policy", "Vendor Terms"]
    assert len(results[0]["excerpts"]) == 2
    assert results[0]["score"] >= results[1]["score"]
```

Run: `pytest tests/test_internal_index.py -q`

Expected: failure because grouped general search is missing.

- [ ] **Step 5: Implement grouped semantic search and verify GREEN**

Query enough top chunks (`limit * excerpts_per_document * 3`), apply the threshold, group by document UUID in Python preserving score order, retain distinct chunk IDs, and stop at both limits.

Run: `pytest tests/analysis/test_internal_documents.py tests/test_internal_index.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/analysis/internal_documents.py backend/analysis/uploads.py internal_index.py tests/analysis/test_internal_documents.py tests/test_internal_index.py
git commit -m "feat: ingest and search internal PDFs"
```

---

### Task 4: Persistent Suggestion Generation

**Files:**
- Create: `backend/analysis/suggestions.py`
- Create: `tests/analysis/test_suggestions.py`

**Interfaces:**
- Produces: `analyze_regulatory_document(document_id: UUID, session: Session, analyze: Callable = analyze_clause_impact) -> int`.
- Produces: `reanalyze_internal_document(document_id: UUID, session: Session) -> int`.
- Produces: `set_suggestion_status(suggestion_id: UUID, status: str, session: Session) -> DocumentSuggestion`.

- [ ] **Step 1: Write failing persistence and lifecycle tests**

```python
def test_analysis_saves_only_affected_matches(session, regulation, internal_chunk, monkeypatch):
    monkeypatch.setattr(suggestions, "find_impacted_assets", lambda *args, **kwargs: [{
        "internal_chunk_id": str(internal_chunk.id), "similarity_score": 0.91,
        "content": internal_chunk.content, "clause_reference": "Clause 1",
    }])
    count = suggestions.analyze_regulatory_document(
        regulation.id, session, analyze=lambda *_: LegalImpactAnalysis(
            is_affected=True, impact_score=8, legal_reasoning="Conflict",
            proposed_amended_clause="New clause", statutory_citations=["s 1"],
        ),
    )
    assert count == 1
    assert session.query(DocumentSuggestion).one().status == "pending"
```

Add tests that a second run updates rather than duplicates pending rows, accepted/dismissed rows remain unchanged, a failed rerun retains old pending rows, unaffected matches are omitted, and invalid status is rejected.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest tests/analysis/test_suggestions.py -q`

Expected: import failure because `suggestions.py` does not exist.

- [ ] **Step 3: Implement staged, idempotent generation**

Load the saved regulatory `Document`, require non-blank `ocr_text`, chunk it, vector-match each clause, and calculate analyses into plain staged records before mutating suggestion rows. Within a nested transaction, update matching pending rows, insert missing rows, and remove obsolete pending rows in scope. Never update or delete accepted/dismissed rows. Generate redlines with `generate_redline_diff` and label the source based on live-client availability.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `pytest tests/analysis/test_suggestions.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/suggestions.py tests/analysis/test_suggestions.py
git commit -m "feat: persist regulatory change suggestions"
```

---

### Task 5: Internal Document HTTP API

**Files:**
- Modify: `backend/api/schemas.py`
- Modify: `backend/api/routes.py`
- Create: `tests/api/test_internal_documents.py`

**Interfaces:**
- Produces all endpoints and response shapes listed in the design specification.
- Produces: `GET /api/v1/documents/{id}/suggestions` returning persisted suggestions for the regulatory impact screen.
- Route dependencies `object_storage()` and `database_session()` are overrideable in tests.
- List query: `q: str | None`, `offset: int = 0`, `limit: int = 50` with limit range 1–100.
- Search body: `{ "query": str, "limit": int = 10 }` with query trimmed and non-blank.

- [ ] **Step 1: Write failing upload/list/detail/search API tests**

```python
def test_upload_returns_created_document(client, monkeypatch):
    monkeypatch.setattr(routes, "ingest_pdf", lambda **kwargs: SimpleNamespace(
        document=document_fixture(), deduplicated=False,
    ))
    response = client.post(
        "/api/v1/internal-documents",
        files={"file": ("policy.pdf", b"%PDF-test", "application/pdf")},
        data={"title": "Operational Policy"},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Operational Policy"
    assert response.json()["deduplicated"] is False
```

Add tests for duplicate 200, newest-first list, 404 detail/delete/reanalysis, internal detail clauses/suggestions, regulatory-document suggestions, presigned URL, grouped search, both re-analysis routes, and status PATCH validation.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest tests/api/test_internal_documents.py -q`

Expected: 404 responses because the routes do not exist.

- [ ] **Step 3: Implement schemas, dependencies, and routes**

Create explicit Pydantic response models rather than returning ORM internals. Read upload bytes with the existing `MAX_UPLOAD_BYTES + 1` guard. Map domain exceptions to 409, 413, 422, and 503 responses. Return a 15-minute presigned URL. Serialize UUIDs and datetimes consistently as strings.

- [ ] **Step 4: Run API and regression tests**

Run: `pytest tests/api/test_internal_documents.py tests/api/test_analysis.py tests/api/test_updates_route.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/schemas.py backend/api/routes.py tests/api/test_internal_documents.py
git commit -m "feat: expose internal document APIs"
```

---

### Task 6: Automatic MAS Pipeline Integration

**Files:**
- Modify: `backend/pipeline.py`
- Modify: `backend/analysis/updates.py`
- Create: `tests/analysis/test_pipeline_suggestions.py`
- Modify: `backend/docs/pipeline.md`
- Modify: `backend/docs/database.md`
- Modify: `README.md`

**Interfaces:**
- Changes: `_upsert_document(...) -> Document` returns the inserted or updated ORM row.
- Consumes: `analyze_regulatory_document(document_id: UUID, session: Session) -> int`.
- Automatic analysis runs only when the saved regulatory row has non-blank `ocr_text`.

- [ ] **Step 1: Write failing pipeline integration tests**

```python
def test_pipeline_generates_suggestions_after_saving_ocr(monkeypatch, session, processed_doc):
    analyzed = []
    monkeypatch.setattr(pipeline, "get_session", fake_session_scope(session))
    monkeypatch.setattr(pipeline, "download_and_ocr", lambda *args: "Section 1. Report promptly.")
    monkeypatch.setattr(pipeline, "process_document", lambda *args: processed_doc)
    monkeypatch.setattr(pipeline, "analyze_regulatory_document", lambda doc_id, session: analyzed.append(doc_id) or 1)
    pipeline.run(json_path=fixture_json, pdf_dir=tmp_path, ocr_dir=tmp_path, limit=None, skip_ocr=False, skip_llm=False)
    assert analyzed == [session.query(Document).one().id]
```

Add tests that blank OCR skips matching and matching exceptions are logged without removing the regulatory record. Cover both CLI ingestion and `/updates` refresh ingestion paths.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest tests/analysis/test_pipeline_suggestions.py -q`

Expected: `_upsert_document` returns `None` and suggestion generation is never called.

- [ ] **Step 3: Integrate best-effort automatic analysis**

Return the ORM row from `_upsert_document`. Flush before analysis so it has an ID. Commit the regulatory transaction, then open a separate session for suggestion generation, ensuring analysis failure cannot roll back regulatory data. Apply the same helper from both pipeline entry points to avoid divergent behavior.

Update docs to describe the now-implemented persistent schema, S3 variables, automatic trigger, and manual recovery route.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `pytest tests/analysis/test_pipeline_suggestions.py tests/analysis/test_updates.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline.py backend/analysis/updates.py backend/docs/pipeline.md backend/docs/database.md README.md tests/analysis/test_pipeline_suggestions.py
git commit -m "feat: analyze internal documents during MAS ingestion"
```

---

### Task 7: Frontend API Client and Internal Document Library

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/api.test.js`
- Create: `frontend/src/hooks/useInternalDocuments.js`
- Create: `frontend/src/components/InternalDocumentsView.jsx`
- Create: `frontend/src/components/InternalDocumentsView.test.jsx`
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/App.test.jsx`

**Interfaces:**
- Produces client functions `fetchInternalDocuments`, `uploadInternalDocument`, `searchInternalDocuments`, `fetchInternalDocument`, `fetchInternalDocumentPdfUrl`, `deleteInternalDocument`, `reanalyzeInternalDocument`, `fetchRegulatorySuggestions`, and `updateSuggestionStatus`.
- Produces `useInternalDocuments()` with `{ documents, loading, error, upload, search, resetSearch, remove }`.
- `InternalDocumentsView` owns `openedId` and preserves inventory/search state while detail is open.

- [ ] **Step 1: Write failing API-client tests**

```javascript
test('uploads a PDF as multipart form data', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, status: 201, json: async () => ({ id: 'doc-1' }) })
  const file = new File(['pdf'], 'policy.pdf', { type: 'application/pdf' })
  await uploadInternalDocument(file, 'Policy')
  const [url, options] = globalThis.fetch.mock.calls[0]
  expect(url).toBe('/api/v1/internal-documents')
  expect(options.method).toBe('POST')
  expect(options.body.get('file')).toBe(file)
  expect(options.body.get('title')).toBe('Policy')
})
```

Add one request-shape/error test per client function.

- [ ] **Step 2: Run client tests and verify RED**

Run: `cd frontend && npm test -- --run src/api.test.js`

Expected: missing exported functions.

- [ ] **Step 3: Implement API functions and hook**

Reuse `readJson`. Do not set `Content-Type` for `FormData`. URL-encode list query parameters. The hook must retain the last good list after upload/search failures and insert a successfully uploaded document only once when `deduplicated` is true.

- [ ] **Step 4: Write failing library/navigation tests**

```javascript
test('opens Internal Documents from the sidebar and uploads a PDF', async () => {
  vi.spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce({ ok: true, json: async () => [] }) // regulatory docs
    .mockResolvedValueOnce({ ok: true, json: async () => [] }) // internal docs
    .mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({
      id: 'doc-1', title: 'Policy', filename: 'policy.pdf', size_bytes: 100,
      chunk_count: 2, status: 'indexed', created_at: '2026-09-06T00:00:00Z', deduplicated: false,
    }) })
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Internal Documents' }))
  fireEvent.change(screen.getByLabelText('Upload PDF'), { target: { files: [new File(['pdf'], 'policy.pdf', { type: 'application/pdf' })] } })
  fireEvent.click(screen.getByRole('button', { name: 'Upload document' }))
  expect(await screen.findByText('Policy')).toBeInTheDocument()
})
```

Add library loading/empty/error, semantic search/reset, duplicate feedback, selection, and responsive row tests.

- [ ] **Step 5: Implement navigation and library UI**

Add `{ id: 'documents', label: 'Internal Documents', icon: Files }` to `NAV` and `documents: 'Internal Documents'` to `TITLES`. Render the view from `App`. Build the table with accessible row buttons, upload progress text, search form, normal/search empty states, and formatted byte size/date.

- [ ] **Step 6: Run tests and verify GREEN**

Run: `cd frontend && npm test -- --run src/api.test.js src/components/InternalDocumentsView.test.jsx src/App.test.jsx`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api.js frontend/src/api.test.js frontend/src/hooks/useInternalDocuments.js frontend/src/components/InternalDocumentsView.jsx frontend/src/components/InternalDocumentsView.test.jsx frontend/src/components/Sidebar.jsx frontend/src/App.jsx frontend/src/App.test.jsx
git commit -m "feat: add internal document library"
```

---

### Task 8: Split PDF, Clauses, and Suggestions Detail View

**Files:**
- Create: `frontend/src/components/InternalDocumentDetail.jsx`
- Create: `frontend/src/components/InternalDocumentDetail.test.jsx`
- Create: `frontend/src/components/SuggestionCard.jsx`
- Modify: `frontend/src/components/InternalDocumentsView.jsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- `InternalDocumentDetail({ documentId, onBack, onDeleted })` fetches detail and PDF URL.
- `SuggestionCard({ suggestion, onStatusChange })` persists review-state changes and renders `Redline`.
- Detail refreshes an expired PDF URL once when the embedded viewer reports a load error.

- [ ] **Step 1: Write failing split-view and interaction tests**

```javascript
test('shows the PDF beside extracted clauses and suggestions', async () => {
  mockDetailRequests()
  render(<InternalDocumentDetail documentId="doc-1" onBack={vi.fn()} onDeleted={vi.fn()} />)
  expect(await screen.findByTitle('Policy PDF')).toHaveAttribute('src', 'https://signed.example/policy.pdf')
  expect(screen.getByText('Clause 1')).toBeInTheDocument()
  expect(screen.getByText('Suggested redline')).toBeInTheDocument()
  expect(screen.getByText('[-three years-]')).toBeInTheDocument()
})
```

Add tests for back, clause filtering, one PDF URL refresh, viewer fallback link, re-analysis loading/success/failure, accepted/dismissed/undo transitions, deletion confirmation/cancel/success, and stacked-view class hooks.

- [ ] **Step 2: Run tests and verify RED**

Run: `cd frontend && npm test -- --run src/components/InternalDocumentDetail.test.jsx`

Expected: import failure because the detail component does not exist.

- [ ] **Step 3: Implement the split view**

Use a two-column CSS grid with `minmax(0, 1.1fr) minmax(22rem, .9fr)`, independent panel scrolling, and a single-column media query at the project mobile breakpoint. Render the PDF in a titled `iframe`; keep clauses and suggestions usable if it fails. Use the existing `Redline`, `Badge`, and `Button` components. Require a native confirmation dialog before calling delete.

- [ ] **Step 4: Replace regulatory mock suggestion data**

Modify `AffectedDocumentsView.jsx` to call `fetchRegulatorySuggestions(regulation.id)` when opened and render the returned persisted rows. Modify `RegulatoryChangesView.jsx` to display `document.suggestion_count`, added to `DocumentResponse` and `_doc_to_dict`, in its Affected column. Remove `mockAffected.js` imports from production components but retain the fixture file until no tests import it.

Write a failing test first asserting an API-provided suggestion title and redline render, verify it fails against mock-backed behavior, then make the change and rerun `RegulatoryChangesView.test.jsx`.

- [ ] **Step 5: Run detail and regression tests**

Run: `cd frontend && npm test -- --run src/components/InternalDocumentDetail.test.jsx src/components/InternalDocumentsView.test.jsx src/components/RegulatoryChangesView.test.jsx src/App.test.jsx`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/InternalDocumentDetail.jsx frontend/src/components/InternalDocumentDetail.test.jsx frontend/src/components/SuggestionCard.jsx frontend/src/components/InternalDocumentsView.jsx frontend/src/components/AffectedDocumentsView.jsx frontend/src/components/RegulatoryChangesView.jsx frontend/src/index.css
git commit -m "feat: add split internal document review view"
```

---

### Task 9: End-to-End Verification and Deployment Contract

**Files:**
- Modify: `tests/test_railway_config.py`
- Modify: `README.md`
- Modify: `backend/docs/database.md`
- Modify: `backend/docs/pipeline.md`

**Interfaces:**
- Deployment documentation maps the five agreed variables to the API service.
- No new Railway worker or cron service is introduced by this feature.

- [ ] **Step 1: Write the failing deployment-contract test**

```python
def test_readme_documents_internal_document_storage_environment():
    readme = Path("README.md").read_text()
    for name in (
        "AWS_ENDPOINT_URL", "S3_BUCKET_NAME", "AWS_DEFAULT_REGION",
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
    ):
        assert name in readme
```

- [ ] **Step 2: Run it and verify RED**

Run: `pytest tests/test_railway_config.py -q`

Expected: missing-variable assertion before the deployment section is finalized.

- [ ] **Step 3: Finalize operator documentation**

Document bucket provisioning, variable references, database migration behavior, the 10 MB/image-only limitation, automatic analysis timing, manual retry routes, and the fact that bucket objects are private and exposed with 15-minute presigned URLs.

- [ ] **Step 4: Run complete backend verification**

Run: `pytest -q`

Expected: all tests PASS with no collection errors.

- [ ] **Step 5: Run complete frontend verification**

Run: `cd frontend && npm test -- --run`

Expected: all Vitest suites PASS.

- [ ] **Step 6: Run the production build**

Run: `cd frontend && npm run build`

Expected: Vite exits 0 and creates `frontend/dist` without unresolved imports.

- [ ] **Step 7: Inspect the final diff**

Run: `git status --short && git diff --check && git diff --stat HEAD~9..HEAD`

Expected: only intended feature/docs changes, no whitespace errors, and no secrets or generated `dist` files staged.

- [ ] **Step 8: Commit final documentation adjustments**

```bash
git add tests/test_railway_config.py README.md backend/docs/database.md backend/docs/pipeline.md
git commit -m "docs: document internal document deployment"
```
