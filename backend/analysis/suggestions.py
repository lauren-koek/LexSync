"""Persisted regulatory-change suggestions backed by pgvector matches."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from backend.analysis import analyse, ingest
from backend.analysis.analyse import LegalImpactAnalysis
from backend.db.models import (
    Document,
    DocumentSuggestion,
    InternalDocument,
    InternalDocumentChunk,
)
from internal_index import embed_text, find_impacted_assets

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
        for match in find_impacted_assets(
            regulation["content"],
            limit=50 if internal_document_id else 3,
            session=session,
            internal_document_id=internal_document_id,
        ):
            match_document_id = UUID(match["internal_document_id"])
            if internal_document_id and match_document_id != internal_document_id:
                continue
            result = analyze(regulation["content"], match["content"])
            if not result.is_affected:
                continue
            staged.append((regulation, match, result))

    deduplicated = {}
    for regulation, match, result in staged:
        key = (
            match["internal_chunk_id"],
            " ".join(result.proposed_amended_clause.lower().split()),
        )
        previous = deduplicated.get(key)
        if previous is None or match["similarity_score"] > previous[1]["similarity_score"]:
            deduplicated[key] = (regulation, match, result)
    staged = list(deduplicated.values())

    changed = 0
    active_keys = set()
    for regulation, match, result in staged:
        chunk_id = UUID(match["internal_chunk_id"])
        chunk = session.get(InternalDocumentChunk, chunk_id)
        if chunk is not None:
            chunk.review_status = "outdated"
            chunk.review_reason = result.legal_reasoning
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


def _rechunk_legacy_document(document: InternalDocument, session: Session) -> None:
    """Split legacy one-chunk uploads now that numbered headings are supported."""
    chunks = list(document.chunks)
    if len(chunks) != 1 or chunks[0].clause_reference != "General":
        return
    raw_chunks = ingest.chunk_legal_document(
        chunks[0].content, "INTERNAL_ASSET", str(document.id)
    )
    if len(raw_chunks) <= 1:
        return
    document.chunks = [
        InternalDocumentChunk(
            title=f"{document.title} — {raw['clause_reference']}",
            clause_reference=raw["clause_reference"],
            content=raw["content"],
            embedding=embed_text(raw["content"]),
        )
        for raw in raw_chunks
    ]
    document.chunk_count = len(raw_chunks)
    session.flush()


def _notice_references(text: str) -> set[str]:
    return {
        match.replace(" ", "").lower()
        for match in re.findall(r"(?:MAS\s+)?Notice\s+\d+[A-Za-z]?", text, re.IGNORECASE)
    }


def _save_document_gaps(
    regulatory: Document,
    internal: InternalDocument,
    session: Session,
) -> int:
    asset_text = "\n\n".join(chunk.content for chunk in internal.chunks)
    references = _notice_references(asset_text)
    searchable_regulation = f"{regulatory.title or ''}\n{regulatory.ocr_text or ''}"
    if references and references.isdisjoint(_notice_references(searchable_regulation)):
        return 0
    if not references:
        return 0

    findings = analyse.analyze_document_gaps(regulatory.ocr_text or "", asset_text)
    if not findings or not internal.chunks:
        return 0
    anchor = internal.chunks[0]
    changed = 0
    for index, finding in enumerate(findings, start=1):
        reference = f"Missing obligation {index}: {(finding.statutory_citations or ['Regulation'])[0]}"
        existing = session.query(DocumentSuggestion).filter_by(
            regulatory_document_id=regulatory.id,
            regulation_clause_reference=reference,
            internal_chunk_id=anchor.id,
        ).first()
        anchor.review_status = "outdated"
        anchor.review_reason = finding.legal_reasoning
        values = {
            "internal_document_id": internal.id,
            "regulation_content": regulatory.ocr_text or "",
            "similarity_score": 1.0,
            "is_affected": True,
            "impact_score": finding.impact_score,
            "legal_reasoning": finding.legal_reasoning,
            "proposed_amended_clause": finding.proposed_amended_clause,
            "statutory_citations": finding.statutory_citations,
            "redline_diff": f"{{+{finding.proposed_amended_clause}+}}",
            "analysis_source": (
                "llm" if analyse._get_instructor_client() is not None else "offline_heuristic"
            ),
        }
        if existing is None:
            session.add(DocumentSuggestion(
                regulatory_document_id=regulatory.id,
                internal_chunk_id=anchor.id,
                regulation_clause_reference=reference,
                status="pending",
                **values,
            ))
        elif existing.status == "pending":
            for name, value in values.items():
                setattr(existing, name, value)
        else:
            continue
        changed += 1
    return changed


def reanalyze_internal_document(
    document_id: UUID,
    session: Session,
    analyze: Callable[[str, str], LegalImpactAnalysis] = analyse.analyze_clause_impact,
) -> dict[str, int]:
    internal = session.get(InternalDocument, document_id)
    if internal is None:
        raise LookupError("Internal document not found")
    _rechunk_legacy_document(internal, session)
    checked_at = datetime.now(UTC)
    for chunk in internal.chunks:
        chunk.review_status = "current"
        chunk.review_reason = "No conflicting or missing regulatory requirement was identified."
        chunk.last_reviewed_at = checked_at

    total = 0
    documents = session.query(Document).filter(Document.ocr_text.is_not(None)).all()
    for document in documents:
        total += analyze_regulatory_document(
            document.id, session, analyze=analyze, internal_document_id=document_id
        )
        total += _save_document_gaps(document, internal, session)
    outdated = sum(chunk.review_status == "outdated" for chunk in internal.chunks)
    internal.status = "outdated" if outdated else "current"
    session.flush()
    return {
        "suggestion_count": total,
        "checked_clause_count": len(internal.chunks),
        "outdated_clause_count": outdated,
    }


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
