# Unified React Resilience Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load saved regulatory documents on startup and recreate the historical Legal Resilience Engine end to end inside the existing React application.

**Architecture:** Add focused database-listing and multipart-analysis boundaries to FastAPI while preserving existing endpoints. Split React into updates and analysis views under persistent top-level state, with safe component-based redline rendering.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy, pytest, React 18, Vite, Vitest, Testing Library, plain CSS

**Spec:** `docs/superpowers/specs/2026-09-05-unified-react-resilience-design.md`

## Global Constraints

- Existing `POST /api/v1/updates` and JSON `POST /api/v1/analysis` contracts remain compatible.
- Saved MAS documents never automatically become analysis inputs.
- Uploaded `.txt` or `.pdf` content takes precedence over pasted text.
- Database results are capped at 50 and ordered newest first.
- Uploaded files are temporary and redlines are rendered without raw HTML injection.

---

### Task 1: Saved document listing API

**Files:**
- Modify: `backend/analysis/updates.py`
- Modify: `backend/api/routes.py`
- Test: `tests/analysis/test_updates.py`
- Test: `tests/api/test_updates_route.py`

**Interfaces:**
- Produces: `list_documents(limit: int = 50) -> list[dict]`
- Produces: `GET /api/v1/documents -> list[DocumentResponse]`

- [ ] **Step 1: Write failing query and route tests**

Add a unit test whose fake SQLAlchemy query verifies descending `Document.date`
and `Document.created_at` ordering plus `limit(50)`, and an API test that patches
`routes.list_documents` and asserts `/api/v1/documents` serializes its result.

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/analysis/test_updates.py tests/api/test_updates_route.py -q`
Expected: collection/import failure because `list_documents` and the route do not exist.

- [ ] **Step 3: Implement the query and route**

Implement:

```python
def list_documents(limit: int = _MAX_RESULTS) -> list[dict]:
    with get_session() as session:
        docs = (
            session.query(Document)
            .order_by(Document.date.desc(), Document.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_doc_to_dict(doc) for doc in docs]
```

Register `@router.get("/documents", response_model=list[DocumentResponse])`.

- [ ] **Step 4: Run tests to verify GREEN**

Run the Task 1 command and expect all tests to pass.

### Task 2: Multipart analysis API

**Files:**
- Create: `backend/analysis/uploads.py`
- Modify: `backend/api/routes.py`
- Modify: `requirements.txt`
- Create: `tests/analysis/test_uploads.py`
- Modify: `tests/api/test_analysis.py`

**Interfaces:**
- Produces: `extract_upload(upload: UploadFile) -> str`
- Produces: `resolve_analysis_text(text: str | None, upload: UploadFile | None, label: str) -> str`
- Produces: `POST /api/v1/analysis/upload -> AnalysisResponse`

- [ ] **Step 1: Write failing extraction and endpoint tests**

Cover `.txt` decoding, `.pdf` delegation through `ingest.extract_text`, rejection
of unsupported/empty input, uploaded-file precedence, and endpoint delegation to
`run_analysis`. Patch embedding/analysis at the API boundary; do not download a model.

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/analysis/test_uploads.py tests/api/test_analysis.py -q`
Expected: import/404 failures for the new upload boundary.

- [ ] **Step 3: Implement request-scoped extraction and route**

Validate suffixes against `{'.txt', '.pdf'}`. Decode text directly. For PDF,
write bytes to `NamedTemporaryFile(suffix='.pdf')`, call `ingest.extract_text`,
and remove the file in `finally`. Raise `HTTPException(422, ...)` for unsupported,
missing, or blank content. Add `python-multipart` to requirements and define the
route with `Form` and `File` fields using the existing identifier defaults.

- [ ] **Step 4: Run tests to verify GREEN**

Run the Task 2 command and expect all tests to pass.

### Task 3: Unified React shell and startup database loading

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/TopBar.jsx`
- Modify: `frontend/src/components/DocumentList.jsx`
- Create: `frontend/src/components/UpdatesView.jsx`
- Create: `frontend/src/App.test.jsx`
- Create: `frontend/src/test/setup.js`
- Modify: `frontend/vite.config.js`

**Interfaces:**
- Consumes: `GET /api/v1/documents`, `POST /api/v1/updates`
- Produces: `fetchDocuments()`, persistent Updates/Analysis navigation

- [ ] **Step 1: Install frontend test dependencies and write failing tests**

Add Vitest, jsdom, `@testing-library/react`, and `@testing-library/jest-dom`.
Test that startup calls `/api/v1/documents`, renders returned document titles,
and navigation switches views without discarding update state.

- [ ] **Step 2: Run tests to verify RED**

Run: `npm test -- --run` from `frontend`.
Expected: failures because startup loading and navigation are absent.

- [ ] **Step 3: Implement API handling and view shell**

Use one response helper that reports non-2xx and malformed JSON clearly.
Refactor update-specific state into `UpdatesView`; startup loads documents in
`useEffect`. A failed scrape retains existing `docs`. Add accessible navigation
buttons with `aria-pressed` state.

- [ ] **Step 4: Run tests to verify GREEN**

Run the Task 3 command and expect all tests to pass.

### Task 4: Historical resilience analysis in React

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/App.jsx`
- Create: `frontend/src/components/AnalysisView.jsx`
- Create: `frontend/src/components/AnalysisResults.jsx`
- Create: `frontend/src/components/Redline.jsx`
- Create: `frontend/src/components/AnalysisView.test.jsx`
- Modify: `frontend/src/App.css`

**Interfaces:**
- Consumes: multipart `POST /api/v1/analysis/upload`
- Produces: editable sample inputs, file selection, pipeline metrics, clause details, safe redlines

- [ ] **Step 1: Write failing analysis UI tests**

Test sample input presence, multipart request fields and file precedence,
loading/error retention, no-match copy, summary metrics, citations, and redline
markers rendered as `<del>` and `<ins>` text nodes.

- [ ] **Step 2: Run tests to verify RED**

Run: `npm test -- --run` from `frontend`.
Expected: component/import failures because the analysis UI is absent.

- [ ] **Step 3: Implement analysis request and presentation**

Build `FormData` with both text fields, identifiers, and optional files. Port
the historical sample inputs and output hierarchy to React. Compute affected
count and highest score from the response. Parse redline markers with a token
regex and render ordinary text, `<del>`, and `<ins>` nodes only.

- [ ] **Step 4: Run tests to verify GREEN**

Run the frontend test command and expect all tests to pass.

### Task 5: End-to-end verification

**Files:**
- Modify only if verification exposes a requirement defect.

- [ ] **Step 1: Run backend verification**

Run: `python -m pytest -q`
Expected: zero failures.

- [ ] **Step 2: Run frontend verification**

Run from `frontend`: `npm test -- --run && npm run build`
Expected: zero test failures and a successful Vite production build.

- [ ] **Step 3: Review the final diff**

Run: `git diff --check && git status --short`
Confirm only spec/plan and intended backend/frontend/test/dependency files changed.
