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


def test_analysis_deduplicates_same_amendment_from_overlapping_regulation_clauses(
    session, records, monkeypatch
):
    regulation, internal, chunk = records
    regulation.ocr_text = "Section 1. Three-fourths approval.\nSection 2. Three-fourths approval."
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

    assert count == 1
    assert session.query(DocumentSuggestion).count() == 1


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


def test_reanalysis_marks_every_clause_current_or_outdated(session, records, monkeypatch):
    regulation, internal, outdated_chunk = records
    current_chunk = InternalDocumentChunk(
        document=internal,
        title="Incident Policy — Clause 2",
        clause_reference="Clause 2",
        content="Clause 2. Staff receive annual training.",
        embedding=[0.0] * 384,
    )
    session.add(current_chunk)
    session.flush()
    monkeypatch.setattr(suggestions, "_rechunk_legacy_document", lambda *args: None)
    monkeypatch.setattr(
        suggestions,
        "find_impacted_assets",
        lambda *args, **kwargs: [{
            "internal_document_id": str(internal.id),
            "internal_chunk_id": str(outdated_chunk.id),
            "similarity_score": 0.91,
            "content": outdated_chunk.content,
            "clause_reference": outdated_chunk.clause_reference,
        }],
    )
    result = suggestions.reanalyze_internal_document(
        internal.id, session, analyze=lambda *_: affected()
    )

    assert result == {"suggestion_count": 1, "checked_clause_count": 2, "outdated_clause_count": 1}
    assert outdated_chunk.review_status == "outdated"
    assert current_chunk.review_status == "current"
    assert outdated_chunk.last_reviewed_at is not None
    assert internal.status == "outdated"


def test_offline_analysis_detects_notice_643_majority_and_reporting_gaps():
    majority = suggestions.analyse._mock_analysis(
        "Paragraph 26 requires approval of a special majority of three-fourths of its board.",
        "Clause 2. Approval requires a simple majority of the Board.",
    )
    reporting = suggestions.analyse.analyze_document_gaps(
        "Paragraph 18. Every exception to the RPT PP must be reported to the board on a quarterly basis.",
        "The policy contains no process for reporting exceptions.",
        client=None,
    )

    assert majority.is_affected is True
    assert "three-fourths" in majority.proposed_amended_clause
    assert len(reporting) == 1
    assert "quarter" in reporting[0].proposed_amended_clause.lower()


def test_document_gap_is_persisted_and_marks_policy_outdated(session, records, monkeypatch):
    regulation, internal, chunk = records
    regulation.title = "Notice 643 Transactions with Related Parties"
    regulation.ocr_text = (
        "MAS Notice 643 paragraph 18 requires every exception to be reported "
        "to the board on a quarterly basis."
    )
    chunk.content += " Regulatory basis: MAS Notice 643."
    finding = suggestions.analyse.MissingObligation(
        impact_score=8,
        legal_reasoning="Quarterly Board reporting is missing.",
        proposed_amended_clause="Report every exception to the Board quarterly.",
        statutory_citations=["MAS Notice 643, paragraph 18"],
    )
    monkeypatch.setattr(suggestions.analyse, "analyze_document_gaps", lambda *_: [finding])
    monkeypatch.setattr(suggestions.analyse, "_get_instructor_client", lambda: None)

    count = suggestions._save_document_gaps(regulation, internal, session)
    session.flush()

    saved = session.query(DocumentSuggestion).one()
    assert count == 1
    assert saved.proposed_amended_clause == "Report every exception to the Board quarterly."
    assert saved.redline_diff.startswith("{+")
    assert chunk.review_status == "outdated"


def test_cited_notice_fast_path_bypasses_vector_search(session, records, monkeypatch):
    regulation, internal, chunk = records
    regulation.title = "Notice 643 Transactions with Related Parties"
    regulation.ocr_text = (
        "MAS Notice 643\n26 A bank must obtain a special majority of "
        "three-fourths of its board."
    )
    chunk.content += " Regulatory basis: MAS Notice 643."
    unrelated = Document(
        source_url="https://mas.example/notice-999",
        title="Notice 999 Unrelated Requirements",
        tags=[], applies_to=[], related_items=[],
        ocr_text="MAS Notice 999\n1 Firms must submit an annual return.",
    )
    session.add(unrelated)
    session.flush()
    observed_regulation_text = []

    def analyze(regulation_text, _asset_text):
        observed_regulation_text.append(regulation_text)
        return LegalImpactAnalysis(
            is_affected=False, impact_score=1, legal_reasoning="Current.",
            proposed_amended_clause=chunk.content, statutory_citations=[],
        )

    monkeypatch.setattr(
        suggestions,
        "find_impacted_assets",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("vector search must not run for an explicitly cited notice")
        ),
    )
    monkeypatch.setattr(suggestions, "_save_document_gaps", lambda *_: 0)

    result = suggestions.reanalyze_internal_document(internal.id, session, analyze=analyze)

    assert result["checked_clause_count"] == 1
    assert observed_regulation_text
    assert any("three-fourths" in text for text in observed_regulation_text)
    assert all("annual return" not in text for text in observed_regulation_text)
