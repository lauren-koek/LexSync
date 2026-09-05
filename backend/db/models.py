from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
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
    title: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[Any] = mapped_column(JSON)
    applies_to: Mapped[Any] = mapped_column(JSON)
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
    # Groups chunks back into their source document (e.g. a filename stem);
    # not a foreign key because internal documents aren't modelled as rows
    # of their own yet — only their chunks are.
    doc_id: Mapped[str] = mapped_column(Text, nullable=False)
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

