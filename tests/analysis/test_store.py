import numpy as np

from backend.analysis import store


class StubEmbedder:
    def __init__(self, vectors: dict[str, list[float]]):
        self.vectors = vectors

    def embed(self, texts: list[str]):
        return iter(np.array(self.vectors[text], dtype=float) for text in texts)


def test_build_index_and_find_impacted_assets_semantically_match_internal_chunks(
    monkeypatch, tmp_path,
):
    monkeypatch.chdir(tmp_path)
    from qdrant_client import QdrantClient

    vectors = {
        "dimension probe": [1.0, 0.0],
        "Regulation privacy clause": [1.0, 0.0],
        "Internal privacy policy": [0.9, 0.1],
        "Internal catering policy": [0.0, 1.0],
        "privacy query": [1.0, 0.0],
    }
    monkeypatch.setattr(store, "get_embedder", lambda: StubEmbedder(vectors), raising=False)
    client = QdrantClient(":memory:")
    chunks = [
        {
            "doc_id": "reg-1",
            "source_type": "REGULATION",
            "title": "Privacy regulation",
            "clause_reference": "Section 1",
            "content": "Regulation privacy clause",
        },
        {
            "doc_id": "asset-1",
            "source_type": "INTERNAL_ASSET",
            "title": "Privacy playbook",
            "clause_reference": "Clause 2",
            "content": "Internal privacy policy",
        },
        {
            "doc_id": "asset-2",
            "source_type": "INTERNAL_ASSET",
            "title": "Catering playbook",
            "clause_reference": "Clause 3",
            "content": "Internal catering policy",
        },
    ]

    indexed_client = store.build_index(chunks, client=client)
    matches = store.find_impacted_assets("privacy query", client=client)

    assert indexed_client is client
    assert matches == [
        {
            "similarity_score": 0.9939,
            "doc_id": "asset-1",
            "source_type": "INTERNAL_ASSET",
            "title": "Privacy playbook",
            "clause_reference": "Clause 2",
            "content": "Internal privacy policy",
        }
    ]
