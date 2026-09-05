"""
store.py — Component 2: Compare & Analyse (Vector Store)

Embeds every clause produced by ingest.py and stores it in an in-memory
Qdrant collection, then answers the core "resilience" question: for a given
regulatory clause, which of our internal documents/playbooks/clauses
*semantically* touch on the same subject matter — even if they use
completely different wording?

Design notes:
- Qdrant's `:memory:` mode + FastEmbed's default ONNX model
  (`BAAI/bge-small-en-v1.5`) means this runs entirely on CPU with no API key,
  no GPU, and no external network call — critical for a reliable live demo.
- We only need cosine similarity search here (no persistence across runs) —
  the collection is rebuilt from ingested_data.json every time this script
  runs, which keeps the pipeline simple and stateless.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models
from rich.console import Console

INPUT_PATH = Path("ingested_data.json")
OUTPUT_PATH = Path("matched_pairs.json")
COLLECTION_NAME = "legal_chunks"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
SIMILARITY_THRESHOLD = 0.50

console = Console()

_embedder: TextEmbedding | None = None
_client: QdrantClient | None = None


def get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
    return _embedder


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(":memory:")
    return _client


def build_index(chunks: list[dict]) -> QdrantClient:
    """Embed every chunk and load it into a fresh in-memory Qdrant collection."""
    client = get_client()
    embedder = get_embedder()

    sample_vector = next(embedder.embed(["dimension probe"]))
    vector_size = len(sample_vector)

    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
    )

    contents = [c["content"] for c in chunks]
    vectors = list(embedder.embed(contents))

    points = [
        models.PointStruct(
            id=i,
            vector=vector.tolist(),
            payload={
                "doc_id": chunk["doc_id"],
                "source_type": chunk["source_type"],
                "title": chunk["title"],
                "clause_reference": chunk["clause_reference"],
                "content": chunk["content"],
            },
        )
        for i, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    console.log(f"[bold green]Indexed[/] {len(points)} clauses into Qdrant ({vector_size}-dim vectors).")
    return client


def find_impacted_assets(regulatory_chunk_text: str, limit: int = 3) -> list[dict]:
    """Vector-search for internal assets semantically related to a regulatory clause.

    Only returns INTERNAL_ASSET chunks scoring >= SIMILARITY_THRESHOLD, so a
    regulation with no real overlap in the internal document set correctly
    returns an empty list rather than forcing a weak match.
    """
    client = get_client()
    embedder = get_embedder()
    query_vector = next(embedder.embed([regulatory_chunk_text])).tolist()

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=models.Filter(
            must=[models.FieldCondition(key="source_type", match=models.MatchValue(value="INTERNAL_ASSET"))]
        ),
        limit=limit,
        score_threshold=SIMILARITY_THRESHOLD,
    ).points

    return [{"similarity_score": round(point.score, 4), **point.payload} for point in results]


def run_matching() -> list[dict]:
    chunks = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    build_index(chunks)

    regulation_chunks = [c for c in chunks if c["source_type"] == "REGULATION"]
    matched_pairs: list[dict] = []

    for reg in regulation_chunks:
        matches = find_impacted_assets(reg["content"])
        console.log(
            f"[cyan]Querying[/] regulation clause [bold]{reg['clause_reference']}[/] "
            f"-> found {len(matches)} candidate internal asset(s)."
        )
        for match in matches:
            matched_pairs.append({
                "regulation": reg,
                "asset": {k: v for k, v in match.items() if k != "similarity_score"},
                "similarity_score": match["similarity_score"],
            })

    OUTPUT_PATH.write_text(json.dumps(matched_pairs, indent=2), encoding="utf-8")
    return matched_pairs


if __name__ == "__main__":
    pairs = run_matching()
    console.print(f"[bold]Wrote {len(pairs)} matched regulation/asset pair(s) to {OUTPUT_PATH.resolve()}[/]")
