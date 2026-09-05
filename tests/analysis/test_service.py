from backend.analysis import service


def test_run_analysis_builds_report_without_writing_artifacts(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    chunks = [
        {
            "id": "reg-1",
            "doc_id": "Reg",
            "source_type": "REGULATION",
            "title": "Reg — Section 1",
            "clause_reference": "Section 1",
            "content": "Section 1. Retain seven years.",
        },
        {
            "id": "asset-1",
            "doc_id": "Asset",
            "source_type": "INTERNAL_ASSET",
            "title": "Asset — Clause 1",
            "clause_reference": "Clause 1",
            "content": "Clause 1. Retain three years.",
        },
    ]
    monkeypatch.setattr(
        service.ingest,
        "chunk_legal_document",
        lambda text, source_type, doc_id: [
            chunk for chunk in chunks if chunk["source_type"] == source_type
        ],
    )
    monkeypatch.setattr(service.store, "build_index", lambda chunks, client=None: object())
    monkeypatch.setattr(
        service.store,
        "find_impacted_assets",
        lambda text, client=None: [{**chunks[1], "similarity_score": 0.8}],
    )
    monkeypatch.setattr(
        service.analyse,
        "analyze_clause_impact",
        lambda regulation, asset: service.analyse.LegalImpactAnalysis(
            is_affected=True,
            impact_score=7,
            legal_reasoning="Changed duration.",
            proposed_amended_clause="Clause 1. Retain seven years.",
            statutory_citations=["Section 1"],
        ),
    )

    result = service.run_analysis("regulation", "asset", "Reg", "Asset")

    assert result["clause_count"] == 2
    assert result["match_count"] == 1
    assert result["report"][0]["analysis"]["impact_score"] == 7
    assert list(tmp_path.iterdir()) == []
