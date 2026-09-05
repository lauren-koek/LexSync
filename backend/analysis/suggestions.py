"""Persisted regulatory-change suggestions backed by pgvector matches."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from backend.analysis import analyse, ingest
from backend.analysis.analyse import LegalImpactAnalysis
from backend.db.models import Document, DocumentSuggestion
from internal_index import find_impacted_assets

REVIEW_STATUSES = {"pending", "accepted", "dismissed"}


def analyze_regulatory_document(
    document_id: UUID,
    session: Session,
    analyze: Callable[[str, str], LegalImpactAnalysis] = analyse.analyze_clause_impact,
    internal_document_id: UUID | None = None,
) -> int:
    document = session.get(Document, document_id)
    if document is None:
        raise LookupError("Regulatory document not found")
    if not (document.ocr_text or "").strip():
        return 0

    regulation_chunks = ingest.chunk_legal_document(
        document.ocr_text, "REGULATION", str(document.id)
    )
    staged = []
    for regulation in regulation_chunks:
        for match in find_impacted_assets(regulation["content"], session=session):
            match_document_id = UUID(match["internal_document_id"])
            if internal_document_id and match_document_id != internal_document_id:
                continue
            result = analyze(regulation["content"], match["content"])
            if not result.is_affected:
                continue
            staged.append((regulation, match, result))

    changed = 0
    active_keys = set()
    for regulation, match, result in staged:
        chunk_id = UUID(match["internal_chunk_id"])
        key = (regulation["clause_reference"], chunk_id)
        active_keys.add(key)
        existing = session.query(DocumentSuggestion).filter_by(
            regulatory_document_id=document.id,
            regulation_clause_reference=regulation["clause_reference"],
            internal_chunk_id=chunk_id,
        ).first()
        if existing is not None and existing.status != "pending":
            continue

        values = {
            "internal_document_id": UUID(match["internal_document_id"]),
            "regulation_content": regulation["content"],
            "similarity_score": match["similarity_score"],
            "is_affected": result.is_affected,
            "impact_score": result.impact_score,
            "legal_reasoning": result.legal_reasoning,
            "proposed_amended_clause": result.proposed_amended_clause,
            "statutory_citations": result.statutory_citations,
            "redline_diff": analyse.generate_redline_diff(
                match["content"], result.proposed_amended_clause
            ),
            "analysis_source": (
                "llm" if analyse._get_instructor_client() is not None else "offline_heuristic"
            ),
        }
        if existing is None:
            existing = DocumentSuggestion(
                regulatory_document_id=document.id,
                internal_chunk_id=chunk_id,
                regulation_clause_reference=regulation["clause_reference"],
                status="pending",
                **values,
            )
            session.add(existing)
        else:
            for name, value in values.items():
                setattr(existing, name, value)
        changed += 1

    pending_query = session.query(DocumentSuggestion).filter_by(
        regulatory_document_id=document.id, status="pending"
    )
    if internal_document_id:
        pending_query = pending_query.filter_by(internal_document_id=internal_document_id)
    for existing in pending_query.all():
        key = (existing.regulation_clause_reference, existing.internal_chunk_id)
        if key not in active_keys:
            session.delete(existing)
    session.flush()
    return changed


def reanalyze_internal_document(document_id: UUID, session: Session) -> int:
    total = 0
    documents = session.query(Document).filter(Document.ocr_text.is_not(None)).all()
    for document in documents:
        total += analyze_regulatory_document(
            document.id, session, internal_document_id=document_id
        )
    return total


def set_suggestion_status(
    suggestion_id: UUID, status: str, session: Session
) -> DocumentSuggestion:
    if status not in REVIEW_STATUSES:
        raise ValueError("Invalid suggestion status")
    suggestion = session.get(DocumentSuggestion, suggestion_id)
    if suggestion is None:
        raise LookupError("Suggestion not found")
    suggestion.status = status
    session.flush()
    return suggestion
