import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.analysis import suggestions
from backend.analysis.analyse import LegalImpactAnalysis
from backend.db.models import (
    Base,
    Document,
    DocumentSuggestion,
    InternalDocument,
    InternalDocumentChunk,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    active = sessionmaker(bind=engine)()
    try:
        yield active
    finally:
        active.close()


@pytest.fixture
def records(session):
    regulation = Document(
        source_url="https://mas.example/change",
        title="New rule",
        tags=[],
        applies_to=[],
        related_items=[],
        ocr_text="Section 1. Report incidents within one day.",
    )
    internal = InternalDocument(
        title="Incident Policy",
        filename="incident.pdf",
        object_key="internal-documents/i/incident.pdf",
        content_type="application/pdf",
        size_bytes=10,
        sha256="a" * 64,
        status="indexed",
        chunk_count=1,
    )
    chunk = InternalDocumentChunk(
        document=internal,
        title="Incident Policy — Clause 1",
        clause_reference="Clause 1",
        content="Clause 1. Report incidents within three days.",
        embedding=[0.0] * 384,
    )
    session.add_all([regulation, internal, chunk])
    session.flush()
    return regulation, internal, chunk


def affected(score=8):
    return LegalImpactAnalysis(
        is_affected=True,
        impact_score=score,
        legal_reasoning="The reporting period conflicts.",
        proposed_amended_clause="Report incidents within one day.",
        statutory_citations=["Section 1"],
    )


def test_analysis_saves_only_affected_matches(session, records, monkeypatch):
    regulation, internal, chunk = records
    monkeypatch.setattr(
        suggestions,
        "find_impacted_assets",
        lambda *args, **kwargs: [{
            "internal_document_id": str(internal.id),
            "internal_chunk_id": str(chunk.id),
            "similarity_score": 0.91,
            "content": chunk.content,
            "clause_reference": chunk.clause_reference,
        }],
    )

    count = suggestions.analyze_regulatory_document(
        regulation.id, session, analyze=lambda *_: affected()
    )

    saved = session.query(DocumentSuggestion).one()
    assert count == 1
    assert saved.status == "pending"
    assert saved.internal_document_id == internal.id
    assert saved.redline_diff


def test_rerun_updates_pending_but_preserves_reviewed_suggestion(
    session, records, monkeypatch
):
    regulation, internal, chunk = records
    monkeypatch.setattr(
        suggestions,
        "find_impacted_assets",
        lambda *args, **kwargs: [{
            "internal_document_id": str(internal.id),
            "internal_chunk_id": str(chunk.id),
            "similarity_score": 0.91,
            "content": chunk.content,
            "clause_reference": chunk.clause_reference,
        }],
    )
    suggestions.analyze_regulatory_document(regulation.id, session, analyze=lambda *_: affected(7))
    saved = session.query(DocumentSuggestion).one()
    saved.status = "accepted"
    session.flush()

    count = suggestions.analyze_regulatory_document(
        regulation.id, session, analyze=lambda *_: affected(10)
    )

    assert count == 0
    assert session.query(DocumentSuggestion).count() == 1
    assert saved.status == "accepted"
    assert saved.impact_score == 7


def test_status_change_rejects_unknown_state(session, records):
    with pytest.raises(ValueError, match="status"):
        suggestions.set_suggestion_status(records[2].id, "archived", session)
