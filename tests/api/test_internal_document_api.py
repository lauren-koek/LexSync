from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.api import routes

client = TestClient(routes.app)


def test_internal_document_collection_route_exists():
    response = client.get("/api/v1/internal-documents")

    assert response.status_code != 404


def test_upload_returns_created_document(monkeypatch):
    document = SimpleNamespace(
        id=uuid4(),
        title="Operational Policy",
        filename="policy.pdf",
        content_type="application/pdf",
        size_bytes=100,
        status="indexed",
        chunk_count=2,
        created_at=None,
        updated_at=None,
    )
    monkeypatch.setattr(
        routes,
        "ingest_pdf",
        lambda **kwargs: SimpleNamespace(document=document, deduplicated=False),
    )
    monkeypatch.setattr(routes, "get_object_storage", lambda: SimpleNamespace())

    response = client.post(
        "/api/v1/internal-documents",
        files={"file": ("policy.pdf", b"%PDF-test", "application/pdf")},
        data={"title": "Operational Policy"},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Operational Policy"
    assert response.json()["deduplicated"] is False


def test_search_rejects_blank_query():
    response = client.post("/api/v1/internal-documents/search", json={"query": "   "})

    assert response.status_code == 422


def test_internal_document_detail_includes_clause_review_status(monkeypatch):
    document = SimpleNamespace(
        id=uuid4(), title="Policy", filename="policy.pdf", content_type="application/pdf",
        size_bytes=100, status="outdated", chunk_count=1, created_at=None, updated_at=None,
        chunks=[SimpleNamespace(
            id=uuid4(), clause_reference="Clause 2", content="Simple majority.",
            review_status="outdated", review_reason="The voting threshold changed.",
            last_reviewed_at=None,
        )], suggestions=[],
    )

    @contextmanager
    def session_scope():
        yield SimpleNamespace(get=lambda *_: document)

    monkeypatch.setattr(routes, "get_session", session_scope)

    response = client.get(f"/api/v1/internal-documents/{document.id}")

    assert response.status_code == 200
    assert response.json()["chunks"][0]["review_status"] == "outdated"
