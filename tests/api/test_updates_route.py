from fastapi.testclient import TestClient

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
        "effective_date": "2026-07-01",
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
    monkeypatch.setattr(routes, "fetch_updates", lambda days, refresh=False: [mock_doc])

    response = client.post("/api/v1/updates", json={"days": 7})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "MAS Circular FAS 11/2026"
    assert body[0]["llm_summary"] == "MAS issued guidance on misconduct reporting."


def test_updates_returns_empty_list_when_no_docs(monkeypatch):
    monkeypatch.setattr(routes, "fetch_updates", lambda days, refresh=False: [])

    response = client.post("/api/v1/updates", json={"days": 7})

    assert response.status_code == 200
    assert response.json() == []


def test_documents_returns_saved_database_documents(monkeypatch):
    saved = {
        "id": "abc-123",
        "title": "Saved circular",
        "date": "2026-09-03",
        "effective_date": "2026-07-01",
        "doc_type": "Circular",
        "topic": "AML",
        "tags": [],
        "applies_to": [],
        "issued_pursuant_to_text": None,
        "issued_pursuant_to": [],
        "source_url": "https://mas.gov.sg/saved",
        "pdf_url": None,
        "llm_summary": "Already processed.",
        "llm_categories": [],
        "llm_impact_check": None,
    }
    monkeypatch.setattr(routes, "list_documents", lambda: [saved], raising=False)

    response = client.get("/api/v1/documents")

    assert response.status_code == 200
    assert response.json() == [saved]
