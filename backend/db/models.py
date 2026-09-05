from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Date, String, Text

# Dimensionality of the vectors written by backend/analysis/internal_index.py.
# Must match whatever embed_text() there returns — a mismatch raises at
# insert time, not silently truncates, so bump both together if you switch
# embedding providers.
INTERNAL_EMBEDDING_DIM = 384


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(100))
    date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    title: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[Any] = mapped_column(JSON)
    applies_to: Mapped[Any] = mapped_column(JSON)
    # Readable "Issued pursuant to" clause plus a list of {section, url} links
    # to the empowering statute provisions on Singapore Statutes Online (SSO).
    issued_pursuant_to_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    issued_pursuant_to: Mapped[Any] = mapped_column(JSON, nullable=True)
    related_items: Mapped[Any] = mapped_column(JSON)
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_categories: Mapped[Any] = mapped_column(JSON, nullable=True)
    llm_impact_check: Mapped[str | None] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    suggestions: Mapped[list["DocumentSuggestion"]] = relationship(
        back_populates="regulatory_document", cascade="all, delete-orphan"
    )


class InternalDocument(Base):
    __tablename__ = "internal_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="indexed")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    chunks: Mapped[list["InternalDocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    suggestions: Mapped[list["DocumentSuggestion"]] = relationship(
        back_populates="internal_document", cascade="all, delete-orphan"
    )


class InternalDocumentChunk(Base):
    """A retrieval-sized clause from an internal legal document, persisted
    alongside its embedding so semantic search survives process restarts.

    This is the "internal-document index" described in
    backend/docs/database.md: unlike `Document` (regulatory PDFs + LLM
    output, plain relational data), every row here carries a pgvector
    column and is queried by nearest-neighbour distance, not by field
    lookup.
    """

    __tablename__ = "internal_document_chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    internal_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("internal_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # Human-readable citation ("Clause 8", "Section 12A (part 2)") carried
    # through from backend/analysis/ingest.py so matches stay traceable to a
    # specific clause instead of just "somewhere in doc X".
    clause_reference: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Fixed-size embedding vector. pgvector's `vector` column type requires
    # the `vector` extension to already exist in the database — see
    # backend/db/session.py:create_tables(), which runs `CREATE EXTENSION
    # IF NOT EXISTS vector` before `Base.metadata.create_all()`.
    embedding: Mapped[list[float]] = mapped_column(
        Vector(INTERNAL_EMBEDDING_DIM), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    document: Mapped[InternalDocument] = relationship(back_populates="chunks")
    suggestions: Mapped[list["DocumentSuggestion"]] = relationship(
        back_populates="internal_chunk", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # HNSW needs no pre-existing data to build (unlike IVFFlat, which
        # wants representative rows to pick centroids), so it's safe to
        # create up front on an empty table. `vector_cosine_ops` matches the
        # cosine-distance operator (`<=>`) used in internal_index.py's query.
        Index(
            "ix_internal_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class DocumentSuggestion(Base):
    __tablename__ = "document_suggestions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    regulatory_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    internal_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("internal_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    internal_chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("internal_document_chunks.id", ondelete="CASCADE"), nullable=False
    )
    regulation_clause_reference: Mapped[str] = mapped_column(Text, nullable=False)
    regulation_content: Mapped[str] = mapped_column(Text, nullable=False)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_affected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    impact_score: Mapped[int] = mapped_column(Integer, nullable=False)
    legal_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_amended_clause: Mapped[str] = mapped_column(Text, nullable=False)
    statutory_citations: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    redline_diff: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_source: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    internal_document: Mapped[InternalDocument] = relationship(back_populates="suggestions")
    internal_chunk: Mapped[InternalDocumentChunk] = relationship(back_populates="suggestions")
    regulatory_document: Mapped[Document] = relationship(back_populates="suggestions")

    __table_args__ = (
        UniqueConstraint(
            "regulatory_document_id",
            "regulation_clause_reference",
            "internal_chunk_id",
            name="uq_document_suggestion_match",
        ),
    )
