"""internal_index.py — PostgreSQL/pgvector-backed internal-document index.

This is the persistent counterpart to the in-memory Qdrant index in
`store.py`. `store.py` re-embeds *both* the regulation and the internal
asset on every request and throws the index away afterwards — fine for a
single request-scoped comparison, but it means internal documents are
never actually indexed anywhere: nothing survives a process restart, and
indexing the same internal document twice means re-embedding it twice.

This module implements the schema `backend/docs/database.md` describes as
"planned": internal-team documents get their own table
(`InternalDocumentChunk`, see backend/db/models.py) with a pgvector
embedding column and an HNSW index, so they can be indexed once and
queried by cosine similarity from any process that shares the database —
independent of FastEmbed, Qdrant, and ONNX Runtime.

Public API (mirrors store.py's shape so callers can switch between the
two without relearning them):
    build_index(chunks)                    -> int   (rows written)
    find_impacted_assets(text, limit=3)    -> list[dict]
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from backend.db.models import InternalDocument, InternalDocumentChunk
from backend.db.session import get_session

# Must match INTERNAL_EMBEDDING_DIM in backend/db/models.py — the pgvector
# column is a fixed width, so every embedding written or queried has to be
# exactly this many components.
EMBEDDING_DIM = 384
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

# Below this cosine similarity, a match is considered noise rather than a
# genuine semantic hit. Mirrors store.py's SIMILARITY_THRESHOLD so results
# from either index are comparable.
SIMILARITY_THRESHOLD = 0.50
_semantic_embedder = None


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def embed_text(text_value: str) -> list[float]:
    """Return a unit-length, EMBEDDING_DIM-wide vector for `text_value`.

    Uses the repository's established local FastEmbed BGE model. If the model
    cannot initialize or infer, it falls back to a deterministic lexical
    vector so offline startup remains available.
    """
    try:
        vector = next(get_semantic_embedder().embed([text_value])).tolist()
        if len(vector) == EMBEDDING_DIM:
            return [float(component) for component in vector]
    except Exception:
        pass
    return _offline_embedding(text_value)


def get_semantic_embedder():
    """Lazily create the process-wide 384-dimension BGE embedder."""
    global _semantic_embedder
    if _semantic_embedder is None:
        from fastembed import TextEmbedding

        _semantic_embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
    return _semantic_embedder


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _offline_embedding(text_value: str) -> list[float]:
    """Deterministic, dependency-free fallback embedding.

    A hashing-trick bag-of-words vector: each lowercased token is hashed
    into one of EMBEDDING_DIM buckets and increments that bucket's count,
    then the vector is L2-normalized so cosine similarity behaves the same
    way it would for a real embedding. This has no notion of meaning —
    "vehicle" and "car" land in unrelated buckets — but it reliably scores
    near-duplicate or reworded clauses (the common case when comparing a
    regulation against an internal template derived from similar
    boilerplate) as similar, and it makes the index fully testable without
    network access or an API key.
    """
    vector = [0.0] * EMBEDDING_DIM
    for token in _TOKEN_RE.findall(text_value.lower()):
        bucket = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % EMBEDDING_DIM
        vector[bucket] += 1.0

    norm = math.sqrt(sum(component * component for component in vector))
    if norm > 0:
        vector = [component / norm for component in vector]
    return vector


# ---------------------------------------------------------------------------
# Session handling
# ---------------------------------------------------------------------------

@contextmanager
def _session_scope(session: Session | None) -> Generator[Session]:
    """Use a caller-supplied session (tests, or a caller already in a
    transaction) as-is, or open+commit a fresh one via get_session()."""
    if session is not None:
        yield session
    else:
        with get_session() as new_session:
            yield new_session


# ---------------------------------------------------------------------------
# Index writes
# ---------------------------------------------------------------------------

def build_index(chunks: list[dict], session: Session | None = None) -> int:
    """Embed and upsert internal-asset chunks into the persistent index.

    Only chunks with source_type == "INTERNAL_ASSET" are indexed here —
    regulations are compared against this index but never stored in it
    (backend/docs/database.md is explicit that regulatory PDFs stay
    ordinary relational data with no vector column).

    Re-indexing a document replaces its rows wholesale: all existing chunks
    for each affected doc_id are deleted before the new ones are inserted,
    so re-running ingestion after a document edit can't leave stale clauses
    (deleted or renumbered sections) behind.
    """
    internal_chunks = [chunk for chunk in chunks if chunk.get("source_type") == "INTERNAL_ASSET"]
    if not internal_chunks:
        return 0

    document_ids = {chunk.get("internal_document_id") for chunk in internal_chunks}
    if None in document_ids:
        raise ValueError("Persistent chunks require internal_document_id")

    with _session_scope(session) as active_session:
        active_session.query(InternalDocumentChunk).filter(
            InternalDocumentChunk.internal_document_id.in_(document_ids)
        ).delete(synchronize_session=False)

        rows = [
            InternalDocumentChunk(
                internal_document_id=chunk["internal_document_id"],
                title=chunk["title"],
                clause_reference=chunk["clause_reference"],
                content=chunk["content"],
                embedding=embed_text(chunk["content"]),
            )
            for chunk in internal_chunks
        ]
        active_session.add_all(rows)

    return len(internal_chunks)


# ---------------------------------------------------------------------------
# Index reads
# ---------------------------------------------------------------------------

def find_impacted_assets(
    regulatory_chunk_text: str,
    limit: int = 3,
    session: Session | None = None,
    internal_document_id=None,
) -> list[dict]:
    """Return internal-asset chunks semantically closest to a regulation
    clause, above SIMILARITY_THRESHOLD, most similar first.

    Shape matches store.py's find_impacted_assets() so either index can
    feed backend/analysis/service.py's report-building loop unchanged.
    """
    query_vector = embed_text(regulatory_chunk_text)

    # `<=>` (cosine distance, via pgvector.sqlalchemy's cosine_distance) is
    # what the HNSW index on InternalDocumentChunk.embedding is built for —
    # ordering by it lets Postgres use the index for an approximate nearest-
    # neighbour scan instead of a full table scan.
    distance_column = InternalDocumentChunk.embedding.cosine_distance(query_vector).label(
        "distance"
    )

    with _session_scope(session) as active_session:
        query = active_session.query(InternalDocumentChunk, distance_column)
        if internal_document_id is not None:
            query = query.filter(
                InternalDocumentChunk.internal_document_id == internal_document_id
            )
        rows = (
            query
            .order_by(distance_column)
            .limit(limit)
            .all()
        )

        results = []
        for chunk, distance in rows:
            similarity_score = 1.0 - float(distance)
            if similarity_score < SIMILARITY_THRESHOLD:
                continue
            results.append(
                {
                    "similarity_score": round(similarity_score, 4),
                    "internal_document_id": str(chunk.internal_document_id),
                    "internal_chunk_id": str(chunk.id),
                    "source_type": "INTERNAL_ASSET",
                    "title": chunk.document.title,
                    "clause_reference": chunk.clause_reference,
                    "content": chunk.content,
                }
            )
        return results


def group_search_rows(
    rows: list[tuple[InternalDocumentChunk, float]],
    limit: int,
    excerpts_per_document: int,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    grouped: dict[str, dict] = {}
    for chunk, distance in rows:
        score = 1.0 - float(distance)
        if score < threshold:
            continue
        key = str(chunk.document.id)
        if key not in grouped:
            if len(grouped) >= limit:
                continue
            grouped[key] = {
                "id": key,
                "title": chunk.document.title,
                "filename": chunk.document.filename,
                "score": round(score, 4),
                "excerpts": [],
            }
        excerpts = grouped[key]["excerpts"]
        if len(excerpts) < excerpts_per_document:
            excerpts.append({
                "chunk_id": str(chunk.id),
                "clause_reference": chunk.clause_reference,
                "content": chunk.content,
                "score": round(score, 4),
            })
    return list(grouped.values())


def semantic_search(
    query: str,
    limit: int = 10,
    excerpts_per_document: int = 3,
    session: Session | None = None,
) -> list[dict]:
    if not query.strip():
        raise ValueError("Search query must not be blank")
    query_vector = embed_text(query)
    distance_column = InternalDocumentChunk.embedding.cosine_distance(query_vector).label(
        "distance"
    )
    with _session_scope(session) as active_session:
        rows = (
            active_session.query(InternalDocumentChunk, distance_column)
            .join(InternalDocument)
            .order_by(distance_column)
            .limit(limit * excerpts_per_document * 3)
            .all()
        )
        return group_search_rows(rows, limit, excerpts_per_document)
