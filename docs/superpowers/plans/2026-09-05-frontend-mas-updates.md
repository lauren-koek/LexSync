# Frontend MAS Updates Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `POST /api/v1/updates` backend endpoint and a React (Vite) frontend that fetches, processes, and displays LLM-summarised MAS regulatory documents filtered by a user-supplied lookback window.

**Architecture:** The backend endpoint reads `mas_regulations_and_guidance.json`, filters by date, skips docs already cached in the DB, runs OCR + LLM summarisation for new ones, and returns a flat list. The React frontend calls this endpoint and renders a two-panel layout (document list + detail view).

**Tech Stack:** Python/FastAPI (backend), React 18, Vite 5, plain CSS (frontend)

## Global Constraints

- Backend follows existing patterns in `backend/api/routes.py` and `backend/pipeline.py`
- Frontend lives in `frontend/` at repo root
- CORS must allow `http://localhost:5173` (Vite dev server default)
- Maximum 50 documents returned per request
- Days input defaults to 7; user can change it to any positive integer
- No authentication required
- Vite proxy routes `/api` → `http://localhost:8000` in dev; `VITE_API_BASE_URL` env var for production

---

## File Map

**Create:**
- `backend/analysis/updates.py` — orchestration: filter JSON, check DB cache, OCR+LLM, upsert, return list
- `tests/analysis/test_updates.py` — unit tests for `fetch_updates`
- `tests/api/test_updates_route.py` — API-level tests for `POST /api/v1/updates`
- `frontend/package.json`
- `frontend/vite.config.js`
- `frontend/index.html`
- `frontend/src/main.jsx`
- `frontend/src/App.jsx`
- `frontend/src/App.css`
- `frontend/src/api.js`
- `frontend/src/components/TopBar.jsx`
- `frontend/src/components/DocumentList.jsx`
- `frontend/src/components/DocumentCard.jsx`
- `frontend/src/components/DetailPanel.jsx`

**Modify:**
- `backend/api/schemas.py` — add `UpdatesRequest`, `DocumentResponse`
- `backend/api/routes.py` — add `POST /api/v1/updates` route
- `backend/main.py` — add CORS middleware

---

## Task 1: `updates.py` — orchestration logic

**Files:**
- Create: `backend/analysis/updates.py`
- Test: `tests/analysis/test_updates.py`

**Interfaces:**
- Produces: `fetch_updates(days: int, json_path: Path = ...) -> list[dict]`
- Each dict has keys: `id`, `title`, `date`, `doc_type`, `topic`, `tags`, `applies_to`, `source_url`, `pdf_url`, `llm_summary`, `llm_categories`, `llm_impact_check`

- [ ] **Step 1: Write the failing tests**

Create `tests/analysis/test_updates.py`:

```python
import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.analysis.updates import fetch_updates, _within_window


# --- _within_window ---

def test_within_window_includes_doc_on_cutoff_day():
    doc = {"date": date.today().strftime("%-d %B %Y")}
    assert _within_window(doc, date.today()) is True


def test_within_window_excludes_doc_before_cutoff():
    past = date.today() - timedelta(days=8)
    doc = {"date": past.strftime("%-d %B %Y")}
    assert _within_window(doc, date.today() - timedelta(days=7)) is False


def test_within_window_returns_false_for_missing_date():
    assert _within_window({}, date.today()) is False


# --- fetch_updates ---

@pytest.fixture
def mas_json(tmp_path):
    recent = (date.today() - timedelta(days=2)).strftime("%-d %B %Y")
    old = (date.today() - timedelta(days=30)).strftime("%-d %B %Y")
    data = {
        "documents": [
            {"url": "https://mas.gov.sg/doc1", "title": "Doc 1", "date": recent,
             "doc_type": "Circular", "topic": "AML", "tags": [], "applies_to": [],
             "related_items": [], "pdf_link": "https://mas.gov.sg/doc1.pdf"},
            {"url": "https://mas.gov.sg/doc2", "title": "Old Doc", "date": old,
             "doc_type": "Notice", "topic": "Tax", "tags": [], "applies_to": [],
             "related_items": [], "pdf_link": None},
        ]
    }
    p = tmp_path / "mas.json"
    p.write_text(json.dumps(data))
    return p


def test_fetch_updates_excludes_old_docs(mas_json):
    mock_existing = MagicMock()
    mock_existing.llm_summary = "cached summary"
    mock_existing.id = "uuid-1"
    mock_existing.title = "Doc 1"
    mock_existing.date = date.today() - timedelta(days=2)
    mock_existing.doc_type = "Circular"
    mock_existing.topic = "AML"
    mock_existing.tags = []
    mock_existing.applies_to = []
    mock_existing.source_url = "https://mas.gov.sg/doc1"
    mock_existing.pdf_url = "https://mas.gov.sg/doc1.pdf"
    mock_existing.llm_categories = ["Financial Services"]
    mock_existing.llm_impact_check = "No impact"

    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_existing

    with patch("backend.analysis.updates.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__ = lambda s: mock_session
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)
        results = fetch_updates(7, json_path=mas_json)

    assert len(results) == 1
    assert results[0]["title"] == "Doc 1"


def test_fetch_updates_uses_cache_when_llm_summary_exists(mas_json):
    mock_existing = MagicMock()
    mock_existing.llm_summary = "cached summary"
    mock_existing.id = "uuid-1"
    mock_existing.title = "Doc 1"
    mock_existing.date = date.today() - timedelta(days=2)
    mock_existing.doc_type = "Circular"
    mock_existing.topic = "AML"
    mock_existing.tags = []
    mock_existing.applies_to = []
    mock_existing.source_url = "https://mas.gov.sg/doc1"
    mock_existing.pdf_url = "https://mas.gov.sg/doc1.pdf"
    mock_existing.llm_categories = ["Financial Services"]
    mock_existing.llm_impact_check = "No impact"

    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_existing

    with patch("backend.analysis.updates.get_session") as mock_get_session, \
         patch("backend.analysis.updates.download_and_ocr") as mock_ocr:
        mock_get_session.return_value.__enter__ = lambda s: mock_session
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)
        results = fetch_updates(7, json_path=mas_json)

    mock_ocr.assert_not_called()
    assert results[0]["llm_summary"] == "cached summary"


def test_fetch_updates_processes_uncached_doc(mas_json):
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = None

    mock_processed = MagicMock()
    mock_processed.llm_summary = "new summary"
    mock_processed.llm_categories = ["AML"]
    mock_processed.llm_impact_check = "Review required"

    with patch("backend.analysis.updates.get_session") as mock_get_session, \
         patch("backend.analysis.updates.download_and_ocr", return_value="raw ocr text"), \
         patch("backend.analysis.updates.process_document", return_value=mock_processed), \
         patch("backend.analysis.updates._upsert_document"):
        mock_get_session.return_value.__enter__ = lambda s: mock_session
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)
        results = fetch_updates(7, json_path=mas_json)

    assert results[0]["llm_summary"] == "new summary"


def test_fetch_updates_returns_empty_when_json_missing(tmp_path):
    results = fetch_updates(7, json_path=tmp_path / "nonexistent.json")
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/Lauren/Desktop/Work/LexSync/LexSync
python -m pytest tests/analysis/test_updates.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError` or `ImportError` for `backend.analysis.updates`

- [ ] **Step 3: Create `backend/analysis/updates.py`**

```python
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from backend.db import Document, get_session
from backend.llm.processor import process_document
from backend.pipeline import _upsert_document, parse_date
from backend.scraper.src.pdf_ocr import download_and_ocr

logger = logging.getLogger(__name__)

_DEFAULT_JSON = Path("backend/scraper/output/mas_regulations_and_guidance.json")
_DEFAULT_PDF_DIR = Path("backend/scraper/output/pdfs")
_DEFAULT_OCR_DIR = Path("backend/scraper/output/ocr")
_MAX_RESULTS = 50


def fetch_updates(days: int, json_path: Path = _DEFAULT_JSON) -> list[dict]:
    cutoff = date.today() - timedelta(days=days)

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("MAS JSON not found: %s", json_path)
        return []

    docs = [d for d in data.get("documents", []) if _within_window(d, cutoff)]
    docs = docs[:_MAX_RESULTS]

    results: list[dict] = []
    for doc in docs:
        url = doc.get("url", "")

        cached: dict | None = None
        with get_session() as session:
            existing = session.query(Document).filter_by(source_url=url).first()
            if existing and existing.llm_summary:
                cached = _doc_to_dict(existing)

        if cached:
            results.append(cached)
            continue

        ocr_text: str | None = None
        pdf_url = doc.get("pdf_link")
        if pdf_url:
            try:
                ocr_text = download_and_ocr(pdf_url, _DEFAULT_PDF_DIR, _DEFAULT_OCR_DIR)
            except Exception:
                logger.warning("OCR failed for %s", url, exc_info=True)

        processed = None
        if ocr_text:
            try:
                processed = process_document(doc, ocr_text)
            except Exception:
                logger.warning("LLM processing failed for %s", url, exc_info=True)

        with get_session() as session:
            _upsert_document(session, doc, ocr_text, processed)
            saved = session.query(Document).filter_by(source_url=url).first()
            if saved:
                results.append(_doc_to_dict(saved))

    return results


def _within_window(doc: dict, cutoff: date) -> bool:
    parsed = parse_date(doc.get("date", ""))
    return parsed is not None and parsed >= cutoff


def _doc_to_dict(doc: Document) -> dict:
    return {
        "id": str(doc.id),
        "title": doc.title,
        "date": doc.date.isoformat() if doc.date else None,
        "doc_type": doc.doc_type,
        "topic": doc.topic,
        "tags": doc.tags or [],
        "applies_to": doc.applies_to or [],
        "source_url": doc.source_url,
        "pdf_url": doc.pdf_url,
        "llm_summary": doc.llm_summary,
        "llm_categories": doc.llm_categories or [],
        "llm_impact_check": doc.llm_impact_check,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/analysis/test_updates.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/updates.py tests/analysis/test_updates.py
git commit -m "feat(backend): add fetch_updates orchestration for MAS doc pipeline"
```

---

## Task 2: Schemas, route, and CORS

**Files:**
- Modify: `backend/api/schemas.py`
- Modify: `backend/api/routes.py`
- Modify: `backend/main.py`
- Test: `tests/api/test_updates_route.py`

**Interfaces:**
- Consumes: `fetch_updates(days: int) -> list[dict]` from Task 1
- Produces: `POST /api/v1/updates` → `list[DocumentResponse]`

- [ ] **Step 1: Write the failing API tests**

Create `tests/api/test_updates_route.py`:

```python
from fastapi.testclient import TestClient
from unittest.mock import patch

import backend.api.routes as routes

client = TestClient(routes.app)


def test_updates_rejects_missing_days():
    response = client.post("/api/v1/updates", json={})
    assert response.status_code == 422


def test_updates_rejects_zero_days():
    response = client.post("/api/v1/updates", json={"days": 0})
    assert response.status_code == 422


def test_updates_rejects_negative_days():
    response = client.post("/api/v1/updates", json={"days": -1})
    assert response.status_code == 422


def test_updates_returns_document_list(monkeypatch):
    mock_doc = {
        "id": "abc-123",
        "title": "MAS Circular FAS 11/2026",
        "date": "2026-09-03",
        "doc_type": "Circular",
        "topic": "AML",
        "tags": ["Financial Services"],
        "applies_to": ["Banks"],
        "source_url": "https://mas.gov.sg/doc1",
        "pdf_url": "https://mas.gov.sg/doc1.pdf",
        "llm_summary": "MAS issued guidance on misconduct reporting.",
        "llm_categories": ["Financial Services"],
        "llm_impact_check": "Review internal procedures.",
    }
    monkeypatch.setattr(routes, "fetch_updates", lambda days: [mock_doc])

    response = client.post("/api/v1/updates", json={"days": 7})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "MAS Circular FAS 11/2026"
    assert body[0]["llm_summary"] == "MAS issued guidance on misconduct reporting."


def test_updates_returns_empty_list_when_no_docs(monkeypatch):
    monkeypatch.setattr(routes, "fetch_updates", lambda days: [])

    response = client.post("/api/v1/updates", json={"days": 7})

    assert response.status_code == 200
    assert response.json() == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/api/test_updates_route.py -v 2>&1 | head -20
```

Expected: `FAIL` — route doesn't exist yet

- [ ] **Step 3: Add schemas to `backend/api/schemas.py`**

Append to the existing file after the last class:

```python
class UpdatesRequest(BaseModel):
    days: int = Field(ge=1, description="Lookback window in days")


class DocumentResponse(BaseModel):
    id: str | None
    title: str | None
    date: str | None
    doc_type: str | None
    topic: str | None
    tags: list[str]
    applies_to: list[str]
    source_url: str
    pdf_url: str | None
    llm_summary: str | None
    llm_categories: list[str]
    llm_impact_check: str | None
```

- [ ] **Step 4: Add route to `backend/api/routes.py`**

Replace the full file contents with:

```python
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.analysis.service import run_analysis
from backend.analysis.updates import fetch_updates
from backend.api.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    DocumentResponse,
    HealthResponse,
    UpdatesRequest,
)

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    return {"status": "ok", "service": "lexsync-backend"}


@router.post("/analysis", response_model=AnalysisResponse)
def analysis(request: AnalysisRequest) -> dict:
    return run_analysis(**request.model_dump())


@router.post("/updates", response_model=list[DocumentResponse])
def updates(request: UpdatesRequest) -> list[dict]:
    return fetch_updates(request.days)


app = FastAPI(title="LexSync Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/api/test_updates_route.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 6: Run the full test suite to check for regressions**

```bash
python -m pytest tests/ -v
```

Expected: all existing tests still PASS

- [ ] **Step 7: Commit**

```bash
git add backend/api/schemas.py backend/api/routes.py
git commit -m "feat(api): add POST /api/v1/updates endpoint with CORS"
```

---

## Task 3: Frontend scaffold (Vite + React)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`

- [ ] **Step 1: Verify Node is available**

```bash
node --version && npm --version
```

Expected: Node ≥ 18, npm ≥ 9

- [ ] **Step 2: Create `frontend/package.json`**

```json
{
  "name": "lexsync-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.2"
  }
}
```

- [ ] **Step 3: Create `frontend/vite.config.js`**

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 4: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>LexSync</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create `frontend/src/main.jsx`**

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './App.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 6: Install dependencies**

```bash
cd frontend && npm install
```

Expected: `node_modules/` created, no errors

- [ ] **Step 7: Create a minimal `frontend/src/App.jsx` to verify the scaffold boots**

```jsx
export default function App() {
  return <div>LexSync loading…</div>
}
```

- [ ] **Step 8: Start dev server and verify it renders**

```bash
npm run dev
```

Open `http://localhost:5173` — should show "LexSync loading…"

Stop the server (`Ctrl+C`) before continuing.

- [ ] **Step 9: Commit**

```bash
cd ..
git add frontend/
git commit -m "feat(frontend): scaffold Vite React app"
```

---

## Task 4: API layer + App shell

**Files:**
- Create: `frontend/src/api.js`
- Replace: `frontend/src/App.jsx`
- Create: `frontend/src/App.css`

**Interfaces:**
- Produces: `fetchUpdates(days: number): Promise<Document[]>` where `Document` is the shape from Task 2's response schema

- [ ] **Step 1: Create `frontend/src/api.js`**

```js
export async function fetchUpdates(days) {
  const res = await fetch('/api/v1/updates', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ days }),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Server error ${res.status}: ${text}`)
  }
  return res.json()
}
```

- [ ] **Step 2: Replace `frontend/src/App.jsx` with the full app shell**

```jsx
import { useState } from 'react'
import { fetchUpdates } from './api.js'
import TopBar from './components/TopBar.jsx'
import DocumentList from './components/DocumentList.jsx'
import DetailPanel from './components/DetailPanel.jsx'

export default function App() {
  const [days, setDays] = useState(7)
  const [docs, setDocs] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [fetched, setFetched] = useState(false)

  async function handleFetch() {
    setLoading(true)
    setError(null)
    setDocs([])
    setSelected(null)
    try {
      const results = await fetchUpdates(days)
      setDocs(results)
      if (results.length > 0) setSelected(results[0])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setFetched(true)
    }
  }

  return (
    <div className="app">
      <TopBar days={days} onDaysChange={setDays} onFetch={handleFetch} loading={loading} />
      <div className="main">
        <DocumentList
          docs={docs}
          selected={selected}
          onSelect={setSelected}
          loading={loading}
          error={error}
          fetched={fetched}
          days={days}
        />
        <DetailPanel doc={selected} />
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create `frontend/src/App.css`**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #f5f5f7;
  color: #1d1d1f;
  height: 100vh;
  overflow: hidden;
}

.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

/* TopBar */
.topbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 24px;
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e5e5ea;
  flex-shrink: 0;
}

.topbar-title {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.3px;
  color: #1d1d1f;
  margin-right: auto;
}

.topbar label {
  font-size: 13px;
  color: #6e6e73;
  display: flex;
  align-items: center;
  gap: 6px;
}

.topbar input[type="number"] {
  width: 60px;
  padding: 5px 8px;
  border: 1px solid #d2d2d7;
  border-radius: 6px;
  font-size: 13px;
  text-align: center;
}

.topbar input[type="number"]:focus {
  outline: none;
  border-color: #0071e3;
}

.fetch-btn {
  padding: 7px 16px;
  background: #0071e3;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}

.fetch-btn:hover:not(:disabled) { background: #0077ed; }
.fetch-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Main layout */
.main {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* Document list */
.doc-list {
  width: 320px;
  flex-shrink: 0;
  overflow-y: auto;
  border-right: 1px solid #e5e5ea;
  background: #fff;
  padding: 12px 0;
}

.doc-list-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #6e6e73;
  font-size: 13px;
  text-align: center;
  padding: 24px;
}

.doc-list-error {
  color: #ff3b30;
  font-size: 13px;
  padding: 16px;
}

/* Document card */
.doc-card {
  padding: 12px 16px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: background 0.1s;
}

.doc-card:hover { background: #f5f5f7; }

.doc-card.selected {
  background: #f0f4ff;
  border-left-color: #0071e3;
}

.doc-card-title {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
  margin-bottom: 4px;
}

.doc-card-meta {
  font-size: 11px;
  color: #6e6e73;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.doc-card-type {
  background: #e5e5ea;
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

/* Detail panel */
.detail-panel {
  flex: 1;
  overflow-y: auto;
  padding: 32px 40px;
}

.detail-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #6e6e73;
  font-size: 14px;
}

.detail-title {
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
  margin-bottom: 8px;
}

.detail-meta {
  font-size: 13px;
  color: #6e6e73;
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid #e5e5ea;
}

.detail-section {
  margin-bottom: 28px;
}

.detail-section-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #6e6e73;
  margin-bottom: 8px;
}

.detail-section p {
  font-size: 14px;
  line-height: 1.7;
  color: #1d1d1f;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  background: #e8f0fe;
  color: #1a56db;
  border-radius: 4px;
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 500;
}

.detail-link {
  font-size: 13px;
  color: #0071e3;
  text-decoration: none;
}

.detail-link:hover { text-decoration: underline; }

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid #d2d2d7;
  border-top-color: #0071e3;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin-right: 8px;
  vertical-align: middle;
}

@keyframes spin { to { transform: rotate(360deg); } }
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api.js frontend/src/App.jsx frontend/src/App.css
git commit -m "feat(frontend): add API layer and app shell"
```

---

## Task 5: Components

**Files:**
- Create: `frontend/src/components/TopBar.jsx`
- Create: `frontend/src/components/DocumentList.jsx`
- Create: `frontend/src/components/DocumentCard.jsx`
- Create: `frontend/src/components/DetailPanel.jsx`

- [ ] **Step 1: Create `frontend/src/components/TopBar.jsx`**

```jsx
export default function TopBar({ days, onDaysChange, onFetch, loading }) {
  return (
    <header className="topbar">
      <span className="topbar-title">LexSync</span>
      <label>
        Last
        <input
          type="number"
          min="1"
          max="365"
          value={days}
          onChange={e => onDaysChange(Number(e.target.value))}
          disabled={loading}
        />
        days
      </label>
      <button className="fetch-btn" onClick={onFetch} disabled={loading}>
        {loading && <span className="spinner" />}
        {loading ? 'Fetching…' : 'Fetch Latest Updates'}
      </button>
    </header>
  )
}
```

- [ ] **Step 2: Create `frontend/src/components/DocumentCard.jsx`**

```jsx
export default function DocumentCard({ doc, selected, onSelect }) {
  return (
    <div
      className={`doc-card ${selected ? 'selected' : ''}`}
      onClick={() => onSelect(doc)}
    >
      <div className="doc-card-title">{doc.title || 'Untitled'}</div>
      <div className="doc-card-meta">
        {doc.date && <span>{doc.date}</span>}
        {doc.doc_type && <span className="doc-card-type">{doc.doc_type}</span>}
        {doc.topic && <span>{doc.topic}</span>}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create `frontend/src/components/DocumentList.jsx`**

```jsx
import DocumentCard from './DocumentCard.jsx'

export default function DocumentList({ docs, selected, onSelect, loading, error, fetched, days }) {
  if (error) {
    return (
      <aside className="doc-list">
        <div className="doc-list-error">Error: {error}</div>
      </aside>
    )
  }

  if (loading) {
    return (
      <aside className="doc-list">
        <div className="doc-list-empty">
          <span className="spinner" /> Processing documents…
        </div>
      </aside>
    )
  }

  if (!fetched) {
    return (
      <aside className="doc-list">
        <div className="doc-list-empty">Click "Fetch Latest Updates" to load MAS documents.</div>
      </aside>
    )
  }

  if (docs.length === 0) {
    return (
      <aside className="doc-list">
        <div className="doc-list-empty">No MAS documents found in the last {days} days.</div>
      </aside>
    )
  }

  return (
    <aside className="doc-list">
      {docs.map(doc => (
        <DocumentCard
          key={doc.id || doc.source_url}
          doc={doc}
          selected={selected?.source_url === doc.source_url}
          onSelect={onSelect}
        />
      ))}
    </aside>
  )
}
```

- [ ] **Step 4: Create `frontend/src/components/DetailPanel.jsx`**

```jsx
export default function DetailPanel({ doc }) {
  if (!doc) {
    return (
      <main className="detail-panel">
        <div className="detail-empty">Select a document to view its summary.</div>
      </main>
    )
  }

  return (
    <main className="detail-panel">
      <h1 className="detail-title">{doc.title || 'Untitled'}</h1>

      <div className="detail-meta">
        {doc.date && <span>{doc.date}</span>}
        {doc.doc_type && <span>{doc.doc_type}</span>}
        {doc.topic && <span>{doc.topic}</span>}
        {doc.source_url && (
          <a className="detail-link" href={doc.source_url} target="_blank" rel="noreferrer">
            Source ↗
          </a>
        )}
      </div>

      {doc.llm_summary && (
        <div className="detail-section">
          <div className="detail-section-label">Summary</div>
          <p>{doc.llm_summary}</p>
        </div>
      )}

      {doc.llm_impact_check && (
        <div className="detail-section">
          <div className="detail-section-label">Impact Check</div>
          <p>{doc.llm_impact_check}</p>
        </div>
      )}

      {doc.llm_categories?.length > 0 && (
        <div className="detail-section">
          <div className="detail-section-label">Categories</div>
          <div className="tag-list">
            {doc.llm_categories.map(c => (
              <span key={c} className="tag">{c}</span>
            ))}
          </div>
        </div>
      )}

      {doc.tags?.length > 0 && (
        <div className="detail-section">
          <div className="detail-section-label">Tags</div>
          <div className="tag-list">
            {doc.tags.map(t => (
              <span key={t} className="tag">{t}</span>
            ))}
          </div>
        </div>
      )}

      {doc.applies_to?.length > 0 && (
        <div className="detail-section">
          <div className="detail-section-label">Applies To</div>
          <div className="tag-list">
            {doc.applies_to.map(a => (
              <span key={a} className="tag">{a}</span>
            ))}
          </div>
        </div>
      )}
    </main>
  )
}
```

- [ ] **Step 5: Start dev server and verify the UI renders correctly**

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173`. You should see:
- Top bar with "LexSync" title, days input showing 7, and "Fetch Latest Updates" button
- Left panel: "Click 'Fetch Latest Updates' to load MAS documents."
- Right panel: "Select a document to view its summary."

Stop the server before continuing.

- [ ] **Step 6: Commit**

```bash
cd ..
git add frontend/src/components/
git commit -m "feat(frontend): add TopBar, DocumentList, DocumentCard, DetailPanel components"
```

---

## Task 6: End-to-end smoke test

- [ ] **Step 1: Start the backend**

```bash
uvicorn backend.api.routes:app --reload --port 8000
```

Leave this running in a separate terminal.

- [ ] **Step 2: Start the frontend**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: Verify health endpoint is reachable**

```bash
curl http://localhost:8000/api/v1/health
```

Expected: `{"status":"ok","service":"lexsync-backend"}`

- [ ] **Step 4: Smoke-test the updates endpoint with 30 days**

```bash
curl -s -X POST http://localhost:8000/api/v1/updates \
  -H "Content-Type: application/json" \
  -d '{"days": 30}' | python3 -m json.tool | head -40
```

Expected: JSON array (may be empty if no docs fall in range — that is correct behaviour)

- [ ] **Step 5: Open the UI at `http://localhost:5173`, enter 30 in the days input, click "Fetch Latest Updates"**

Verify:
- Button shows spinner and "Fetching…" while loading
- If results: document cards appear in left panel; clicking one populates the right panel with summary, impact check, and category tags
- If no results: "No MAS documents found in the last 30 days." message appears

- [ ] **Step 6: Commit smoke-test confirmation (no code change needed — just a marker commit)**

```bash
git commit --allow-empty -m "chore: smoke test passed — frontend and backend integrated"
```
