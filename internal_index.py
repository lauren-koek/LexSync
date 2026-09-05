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

from backend.db.models import InternalDocumentChunk
from backend.db.session import get_session
from backend.llm import client as llm_client

# Must match INTERNAL_EMBEDDING_DIM in backend/db/models.py — the pgvector
# column is a fixed width, so every embedding written or queried has to be
# exactly this many components.
EMBEDDING_DIM = 384

# Below this cosine similarity, a match is considered noise rather than a
# genuine semantic hit. Mirrors store.py's SIMILARITY_THRESHOLD so results
# from either index are comparable.
SIMILARITY_THRESHOLD = 0.50


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def embed_text(text_value: str) -> list[float]:
    """Return a unit-length, EMBEDDING_DIM-wide vector for `text_value`.

    Tries a hosted embedding model first (real semantic embeddings); if no
    API key is configured or the request fails for any reason (network,
    rate limit, provider outage), falls back to a deterministic offline
    embedding. This is the same "never hard-fail without a key" contract
    `analyse.py` uses for its mock LLM analysis — the index stays usable
    for demos and tests with zero external setup, at the cost of the
    offline vectors only capturing literal word overlap rather than
    genuine semantic similarity.
    """
    remote_vector = _fetch_remote_embedding(text_value)
    if remote_vector is not None:
        return remote_vector
    return _offline_embedding(text_value)


def _fetch_remote_embedding(text_value: str) -> list[float] | None:
    """Call the hosted embeddings endpoint via the shared OpenRouter client
    (backend/llm/client.py). Returns None on any failure — no API key
    configured, network error, or a provider response client.embed()
    couldn't parse — so the caller can fall back to the offline embedding
    instead of the whole index write/read failing.
    """
    try:
        vector = llm_client.embed(text_value, dimensions=EMBEDDING_DIM)
    except Exception:
        return None

    # A provider that ignores `dimensions` (or a misconfigured model name)
    # would otherwise write a vector pgvector rejects at insert time — bail
    # out to the offline fallback instead of crashing the caller.
    if len(vector) != EMBEDDING_DIM:
        return None
    return [float(component) for component in vector]


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

    doc_ids = {chunk["doc_id"] for chunk in internal_chunks}

    with _session_scope(session) as active_session:
        active_session.query(InternalDocumentChunk).filter(
            InternalDocumentChunk.doc_id.in_(doc_ids)
        ).delete(synchronize_session=False)

        rows = [
            InternalDocumentChunk(
                doc_id=chunk["doc_id"],
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
        rows = (
            active_session.query(InternalDocumentChunk, distance_column)
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
                "doc_id": chunk.doc_id,
                "source_type": "INTERNAL_ASSET",
                "title": chunk.title,
                "clause_reference": chunk.clause_reference,
                "content": chunk.content,
            }
        )
    return results
