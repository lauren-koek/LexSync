"""In-memory semantic matching for regulation and internal-asset clauses."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastembed import TextEmbedding
    from qdrant_client import QdrantClient

COLLECTION_NAME = "legal_chunks"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
SIMILARITY_THRESHOLD = 0.50

_embedder: TextEmbedding | None = None
_client: QdrantClient | None = None


def get_embedder() -> TextEmbedding:
    """Return the process-wide local text embedder, creating it on first use."""
    from fastembed import TextEmbedding

    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
    return _embedder


def get_client() -> QdrantClient:
    """Return the process-wide in-memory vector store."""
    from qdrant_client import QdrantClient

    global _client
    if _client is None:
        _client = QdrantClient(":memory:")
    return _client


def build_index(chunks: list[dict], client: Any = None) -> QdrantClient:
    """Embed all chunks and load them into a fresh in-memory collection."""
    from qdrant_client import models

    active_client = client or get_client()
    embedder = get_embedder()

    sample_vector = next(embedder.embed(["dimension probe"]))
    vector_size = len(sample_vector)

    if active_client.collection_exists(COLLECTION_NAME):
        active_client.delete_collection(COLLECTION_NAME)
    active_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=vector_size,
            distance=models.Distance.COSINE,
        ),
    )

    vectors = embedder.embed([chunk["content"] for chunk in chunks])
    points = [
        models.PointStruct(
            id=index,
            vector=vector.tolist(),
            payload={
                "doc_id": chunk["doc_id"],
                "source_type": chunk["source_type"],
                "title": chunk["title"],
                "clause_reference": chunk["clause_reference"],
                "content": chunk["content"],
            },
        )
        for index, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]

    if points:
        active_client.upsert(collection_name=COLLECTION_NAME, points=points)
    return active_client


def find_impacted_assets(
    regulatory_chunk_text: str,
    limit: int = 3,
    client: Any = None,
) -> list[dict]:
    """Return semantically related internal assets above the match threshold."""
    from qdrant_client import models

    active_client = client or get_client()
    query_vector = next(get_embedder().embed([regulatory_chunk_text])).tolist()

    results = active_client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="source_type",
                    match=models.MatchValue(value="INTERNAL_ASSET"),
                )
            ]
        ),
        limit=limit,
        score_threshold=SIMILARITY_THRESHOLD,
    ).points

    return [
        {"similarity_score": round(point.score, 4), **point.payload}
        for point in results
    ]
