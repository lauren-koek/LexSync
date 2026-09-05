"""Request-local orchestration for legal resilience analysis."""

from backend.analysis import analyse, ingest, notify, store


def run_analysis(
    regulation_text: str,
    internal_asset_text: str,
    regulation_id: str,
    asset_id: str,
) -> dict:
    """Analyze supplied texts without reading or writing shared artifacts."""
    regulation_chunks = ingest.chunk_legal_document(
        regulation_text, "REGULATION", regulation_id
    )
    asset_chunks = ingest.chunk_legal_document(
        internal_asset_text, "INTERNAL_ASSET", asset_id
    )
    chunks = [*regulation_chunks, *asset_chunks]

    store.build_index(chunks)

    using_live_llm = analyse._get_instructor_client() is not None
    report: list[dict] = []
    for regulation in regulation_chunks:
        matches = store.find_impacted_assets(regulation["content"])
        for match in matches:
            asset = {key: value for key, value in match.items() if key != "similarity_score"}
            analysis = analyse.analyze_clause_impact(
                regulation["content"], asset["content"]
            )
            report.append(
                {
                    "regulation": regulation,
                    "asset": asset,
                    "similarity_score": match["similarity_score"],
                    "analysis": analysis.model_dump(),
                    "redline_diff": analyse.generate_redline_diff(
                        asset["content"], analysis.proposed_amended_clause
                    ),
                    "analysis_source": "llm" if using_live_llm else "offline_heuristic",
                }
            )

    return {
        "regulation_id": regulation_id,
        "asset_id": asset_id,
        "clause_count": len(chunks),
        "match_count": len(report),
        "report": report,
        "propagation": notify.summarize_updates(report, dry_run=True),
    }
