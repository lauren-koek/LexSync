
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.analysis import internal_documents
from backend.db.models import Base, InternalDocument, InternalDocumentChunk


class FakeStorage:
    def __init__(self):
        self.puts = []
        self.deletes = []

    def put(self, key, content, content_type):
        self.puts.append((key, content, content_type))

    def delete(self, key):
        self.deletes.append(key)

    def presigned_get_url(self, key, expires_seconds=900):
        return f"signed://{key}"


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    active = sessionmaker(bind=engine)()
    try:
        yield active
    finally:
        active.close()


def test_ingest_pdf_uploads_and_saves_all_chunks(session, monkeypatch):
    storage = FakeStorage()
    monkeypatch.setattr(
        internal_documents,
        "extract_pdf_bytes",
        lambda _: "Clause 1. Keep records.\nClause 2. Report breaches.",
    )

    result = internal_documents.ingest_pdf(
        filename="policy.pdf",
        content_type="application/pdf",
        content=b"%PDF-1.4 test",
        title="Policy",
        storage=storage,
        session=session,
        embed=lambda text: [0.0] * 384,
    )

    assert result.deduplicated is False
    assert result.document.chunk_count == 2
    assert session.query(InternalDocument).count() == 1
    assert session.query(InternalDocumentChunk).count() == 2
    assert storage.puts[0][0].startswith(f"internal-documents/{result.document.id}/")


def test_duplicate_digest_does_not_upload_or_embed(session, monkeypatch):
    storage = FakeStorage()
    monkeypatch.setattr(internal_documents, "extract_pdf_bytes", lambda _: "Clause 1. Text")
    embedded = []
    kwargs = dict(
        filename="policy.pdf",
        content_type="application/pdf",
        content=b"%PDF-same",
        title=None,
        storage=storage,
        session=session,
        embed=lambda text: embedded.append(text) or [0.0] * 384,
    )

    first = internal_documents.ingest_pdf(**kwargs)
    second = internal_documents.ingest_pdf(**kwargs)

    assert second.document.id == first.document.id
    assert second.deduplicated is True
    assert len(storage.puts) == 1
    assert len(embedded) == 1


@pytest.mark.parametrize(
    ("filename", "content_type", "content", "message"),
    [
        ("policy.txt", "application/pdf", b"%PDF-x", "PDF file"),
        ("policy.pdf", "text/plain", b"%PDF-x", "application/pdf"),
        ("policy.pdf", "application/pdf", b"not-pdf", "signature"),
        ("policy.pdf", "application/pdf", b"%PDF-x" + b"x" * (10 * 1024 * 1024), "10 MB"),
    ],
)
def test_ingest_pdf_rejects_invalid_uploads(
    session, filename, content_type, content, message
):
    with pytest.raises(internal_documents.InternalDocumentValidationError, match=message):
        internal_documents.ingest_pdf(
            filename, content_type, content, None, FakeStorage(), session,
            embed=lambda text: [0.0] * 384,
        )


def test_ingest_pdf_rejects_wrong_embedding_dimension(session, monkeypatch):
    storage = FakeStorage()
    monkeypatch.setattr(internal_documents, "extract_pdf_bytes", lambda _: "Clause 1. Text")

    with pytest.raises(internal_documents.InternalDocumentValidationError, match="384"):
        internal_documents.ingest_pdf(
            "policy.pdf", "application/pdf", b"%PDF-x", None, storage, session,
            embed=lambda text: [0.0] * 3,
        )

    assert storage.puts == []


def test_database_failure_deletes_only_new_object(session, monkeypatch):
    storage = FakeStorage()
    monkeypatch.setattr(internal_documents, "extract_pdf_bytes", lambda _: "Clause 1. Text")
    original_flush = session.flush
    flushes = 0

    def fail_persistence_flush(*args, **kwargs):
        nonlocal flushes
        flushes += 1
        if flushes == 2:
            raise RuntimeError("database unavailable")
        return original_flush(*args, **kwargs)

    monkeypatch.setattr(session, "flush", fail_persistence_flush)

    with pytest.raises(RuntimeError, match="database unavailable"):
        internal_documents.ingest_pdf(
            "policy.pdf", "application/pdf", b"%PDF-x", None, storage, session,
            embed=lambda text: [0.0] * 384,
        )

    assert storage.deletes == [storage.puts[0][0]]
