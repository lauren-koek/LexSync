from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.api import routes
from backend.storage import ObjectStorageError

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


def test_internal_document_detail_restores_missing_clause_rows(monkeypatch):
    document = SimpleNamespace(
        id=uuid4(), title="Policy", filename="policy.pdf", object_key="internal-documents/id/policy.pdf",
        content_type="application/pdf", size_bytes=100, status="indexed", chunk_count=2,
        created_at=None, updated_at=None, chunks=[], suggestions=[],
    )

    @contextmanager
    def session_scope():
        yield SimpleNamespace(get=lambda *_: document)

    def restore(target, storage, session):
        target.chunks = [SimpleNamespace(
            id=uuid4(), clause_reference="Clause 1", content="Keep records.",
            review_status="not_checked", review_reason=None, last_reviewed_at=None,
        )]
        target.chunk_count = 1

    monkeypatch.setattr(routes, "get_session", session_scope)
    monkeypatch.setattr(routes, "get_object_storage", lambda: SimpleNamespace())
    monkeypatch.setattr(routes, "restore_missing_chunks", restore)

    response = client.get(f"/api/v1/internal-documents/{document.id}")

    assert response.status_code == 200
    assert response.json()["chunks"][0]["clause_reference"] == "Clause 1"


def test_pdf_url_returns_not_found_when_database_key_has_no_object(monkeypatch):
    document = SimpleNamespace(id=uuid4(), object_key="internal-documents/id/missing.pdf")

    @contextmanager
    def session_scope():
        yield SimpleNamespace(get=lambda *_: document)

    storage = SimpleNamespace(
        exists=lambda _key: False,
        presigned_get_url=lambda *_: "https://storage.example/missing.pdf",
    )
    monkeypatch.setattr(routes, "get_session", session_scope)
    monkeypatch.setattr(routes, "get_object_storage", lambda: storage)

    response = client.get(f"/api/v1/internal-documents/{document.id}/pdf-url")

    assert response.status_code == 404
    assert response.json()["detail"] == "Stored PDF is unavailable"


def test_delete_removes_database_record_even_when_object_is_already_unavailable(monkeypatch):
    document_id = uuid4()
    documents = {
        document_id: SimpleNamespace(
            id=document_id, object_key="internal-documents/id/missing.pdf"
        )
    }

    class FakeSession:
        def get(self, _model, key):
            return documents.get(key)

        def delete(self, document):
            documents.pop(document.id)

        def flush(self):
            pass

    @contextmanager
    def session_scope():
        yield FakeSession()

    class MissingObjectStorage:
        def delete(self, _key):
            raise ObjectStorageError("object is already missing")

    monkeypatch.setattr(routes, "get_session", session_scope)
    monkeypatch.setattr(routes, "get_object_storage", lambda: MissingObjectStorage())

    response = routes.remove_internal_document(document_id)

    assert response.status_code == 204
    assert document_id not in documents
