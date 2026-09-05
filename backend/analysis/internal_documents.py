"""Synchronous ingestion and lifecycle operations for internal PDFs."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from backend.analysis.ingest import chunk_legal_document
from backend.analysis.uploads import (
    MAX_UPLOAD_BYTES,
    PDFExtractionError,
    extract_pdf_bytes,
)
from backend.db.models import InternalDocument, InternalDocumentChunk
from backend.storage.objects import ObjectStorage
from internal_index import EMBEDDING_DIM, embed_text


class InternalDocumentValidationError(ValueError):
    pass


@dataclass(frozen=True)
class IngestionResult:
    document: InternalDocument
    deduplicated: bool


def _safe_filename(filename: str) -> str:
    basename = Path(filename or "document.pdf").name
    cleaned = re.sub(r"[^A-Za-z0-9 ._-]", "_", basename).strip(" .")
    return cleaned or "document.pdf"


def _validate_upload(filename: str, content_type: str, content: bytes) -> str:
    safe_name = _safe_filename(filename)
    if Path(safe_name).suffix.lower() != ".pdf":
        raise InternalDocumentValidationError("Upload a PDF file")
    if content_type != "application/pdf":
        raise InternalDocumentValidationError("PDF content type must be application/pdf")
    if len(content) > MAX_UPLOAD_BYTES:
        raise InternalDocumentValidationError("PDF exceeds the 10 MB limit")
    if not content.startswith(b"%PDF-"):
        raise InternalDocumentValidationError("PDF signature is invalid")
    return safe_name


def ingest_pdf(
    filename: str,
    content_type: str,
    content: bytes,
    title: str | None,
    storage: ObjectStorage,
    session: Session,
    embed: Callable[[str], list[float]] = embed_text,
) -> IngestionResult:
    safe_name = _validate_upload(filename, content_type, content)
    digest = hashlib.sha256(content).hexdigest()
    existing = session.query(InternalDocument).filter_by(sha256=digest).first()
    if existing is not None:
        return IngestionResult(existing, True)

    try:
        extracted = extract_pdf_bytes(content)
    except PDFExtractionError as exc:
        raise InternalDocumentValidationError(str(exc)) from exc

    document_id = uuid4()
    display_title = (title or "").strip() or Path(safe_name).stem
    raw_chunks = chunk_legal_document(
        extracted, "INTERNAL_ASSET", str(document_id)
    )
    prepared = []
    for raw in raw_chunks:
        vector = [float(value) for value in embed(raw["content"])]
        if len(vector) != EMBEDDING_DIM:
            raise InternalDocumentValidationError(
                f"Embedding must contain exactly {EMBEDDING_DIM} dimensions"
            )
        prepared.append((raw, vector))

    object_key = f"internal-documents/{document_id}/{safe_name}"
    storage.put(object_key, content, "application/pdf")
    document = InternalDocument(
        id=document_id,
        title=display_title,
        filename=safe_name,
        object_key=object_key,
        content_type="application/pdf",
        size_bytes=len(content),
        sha256=digest,
        status="indexed",
        chunk_count=len(prepared),
    )
    document.chunks = [
        InternalDocumentChunk(
            title=f"{display_title} — {raw['clause_reference']}",
            clause_reference=raw["clause_reference"],
            content=raw["content"],
            embedding=vector,
        )
        for raw, vector in prepared
    ]
    session.add(document)
    try:
        session.flush()
    except Exception:
        try:
            storage.delete(object_key)
        finally:
            raise
    return IngestionResult(document, False)


def restore_missing_chunks(
    document: InternalDocument,
    storage: ObjectStorage,
    session: Session,
    embed: Callable[[str], list[float]] = embed_text,
) -> int:
    """Rebuild clause rows from the original object after legacy migration loss."""
    if document.chunks:
        return len(document.chunks)
    extracted = extract_pdf_bytes(storage.get(document.object_key))
    raw_chunks = chunk_legal_document(extracted, "INTERNAL_ASSET", str(document.id))
    restored = []
    for raw in raw_chunks:
        vector = [float(value) for value in embed(raw["content"])]
        if len(vector) != EMBEDDING_DIM:
            raise InternalDocumentValidationError(
                f"Embedding must contain exactly {EMBEDDING_DIM} dimensions"
            )
        restored.append(InternalDocumentChunk(
            title=f"{document.title} — {raw['clause_reference']}",
            clause_reference=raw["clause_reference"],
            content=raw["content"],
            embedding=vector,
        ))
    document.chunks = restored
    document.chunk_count = len(restored)
    session.flush()
    return len(restored)


def delete_internal_document(
    document_id: UUID, storage: ObjectStorage, session: Session
) -> None:
    document = session.get(InternalDocument, document_id)
    if document is None:
        raise LookupError("Internal document not found")
    storage.delete(document.object_key)
    session.delete(document)
    session.flush()
