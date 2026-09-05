# LexSync Frontend — MAS Updates Viewer

**Date:** 2026-09-05
**Status:** Approved

---

## Overview

A React (Vite) single-page app in `/frontend` that lets users trigger a filtered scrape of MAS regulatory documents and view LLM-generated summaries for each result. The user selects a lookback window (default 7 days), clicks "Fetch Latest Updates", and sees a two-panel view of the returned documents.

---

## Backend Changes

### New endpoint: `POST /api/v1/updates`

**Request body:**
```json
{ "days": 7 }
```

**Behaviour:**
1. Read `backend/scraper/output/mas_regulations_and_guidance.json`
2. Filter documents whose parsed `date` (format: `"DD Month YYYY"`) falls within the last `days` days from today
3. For each filtered document:
   - Query DB by `source_url`; if a record exists with a non-null `llm_summary`, skip processing and use cached DB record
   - Otherwise: call `download_and_ocr()` then `process_document()` (from `backend/llm/processor.py`, uses `newsletter_prompt.py`)
   - Upsert to DB via existing `_upsert_document()` logic in `backend/pipeline.py`
4. Return all matching documents (cached + newly processed)

**Response schema (list):**
```json
[
  {
    "id": "uuid",
    "title": "string",
    "date": "string",
    "doc_type": "string",
    "topic": "string",
    "tags": ["string"],
    "applies_to": ["string"],
    "source_url": "string",
    "pdf_url": "string | null",
    "llm_summary": "string | null",
    "llm_categories": ["string"],
    "llm_impact_check": "string | null"
  }
]
```

**New files:**
- `backend/api/schemas.py` — add `UpdatesRequest` and `DocumentResponse` Pydantic models
- `backend/api/routes.py` — add `POST /api/v1/updates` route
- `backend/analysis/updates.py` — orchestration logic (filter, skip-if-cached, process, upsert, return)

---

## Frontend

**Stack:** React 18, Vite, plain CSS (no UI library)

**Structure:**
```
frontend/
  index.html
  src/
    main.jsx
    App.jsx
    components/
      TopBar.jsx        # title, days input, fetch button, loading state
      DocumentList.jsx  # scrollable list of document cards
      DocumentCard.jsx  # title, date, doc_type, topic pill
      DetailPanel.jsx   # selected doc: summary, impact check, category tags
    api.js              # fetchUpdates(days) → POST /api/v1/updates
  vite.config.js
  package.json
```

**Layout:**
```
┌─────────────────────────────────────────────────┐
│ LexSync          [Days: 7 ▼]  [Fetch Updates]   │  ← TopBar
├──────────────────┬──────────────────────────────┤
│ Document List    │ Detail Panel                 │
│                  │                              │
│ ┌──────────────┐ │  Title                       │
│ │ Title        │ │  Date · Type · Topic         │
│ │ Date · Type  │ │                              │
│ └──────────────┘ │  Summary                     │
│ ┌──────────────┐ │  ─────────────────           │
│ │ ...          │ │  Impact Check                │
│ └──────────────┘ │  ─────────────────           │
│                  │  Categories: [tag] [tag]     │
└──────────────────┴──────────────────────────────┘
```

**States:**
- **Idle** (initial): prompt to click Fetch
- **Loading**: spinner in list panel, button disabled
- **Results**: document list populated, first item auto-selected
- **Empty**: "No MAS documents found in the last N days"
- **Error**: inline error message with reason

**API config:** Vite proxy `/api` → `http://localhost:8000` in dev. Production URL via `VITE_API_BASE_URL` env var.

---

## Constraints

- No authentication required (internal tool)
- No pagination — if date window returns >50 docs, truncate at 50 with a notice
- CORS must be enabled on the FastAPI app for `http://localhost:5173`
- The Playwright scraper is not triggered by this endpoint — it reads the existing `mas_regulations_and_guidance.json`. Re-scraping MAS is a separate concern.
