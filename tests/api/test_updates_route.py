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
