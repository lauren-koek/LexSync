from pathlib import Path

from fastapi.testclient import TestClient

import backend.api.routes as routes

client = TestClient(routes.app)


def test_analysis_rejects_missing_regulation_text():
    response = client.post(
        "/api/v1/analysis",
        json={"internal_asset_text": "Clause 8. Keep logs."},
    )

    assert response.status_code == 422


def test_analysis_rejects_whitespace_only_asset_text():
    response = client.post(
        "/api/v1/analysis",
        json={"regulation_text": "Section 12A.", "internal_asset_text": "   "},
    )

    assert response.status_code == 422


def test_analysis_returns_frontend_contract(monkeypatch):
    monkeypatch.setattr(
        routes,
        "run_analysis",
        lambda **kwargs: {
            "regulation_id": kwargs["regulation_id"],
            "asset_id": kwargs["asset_id"],
            "clause_count": 2,
            "match_count": 1,
            "report": [
                {
                    "regulation": {"content": "Section 12A."},
                    "asset": {"content": "Clause 8."},
                    "similarity_score": 0.81,
                    "analysis": {
                        "is_affected": True,
                        "impact_score": 7,
                        "legal_reasoning": "A retention period changed.",
                        "proposed_amended_clause": "Retain for seven years.",
                        "statutory_citations": ["Section 12A"],
                    },
                    "redline_diff": "[-three years-] {+seven years+}",
                    "analysis_source": "offline_heuristic",
                }
            ],
            "propagation": {
                "dispatched": 1,
                "dry_run": True,
                "timestamp": "2026-09-05T00:00:00+00:00",
            },
        },
    )

    response = client.post(
        "/api/v1/analysis",
        json={
            "regulation_text": "Section 12A.",
            "internal_asset_text": "Clause 8.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["regulation_id"] == "Uploaded_Regulation"
    assert body["asset_id"] == "Uploaded_Internal_Asset"
    assert body["report"][0]["analysis"]["impact_score"] == 7


def test_analysis_does_not_write_shared_artifacts(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        routes,
        "run_analysis",
        lambda **kwargs: {
            "regulation_id": kwargs["regulation_id"],
            "asset_id": kwargs["asset_id"],
            "clause_count": 0,
            "match_count": 0,
            "report": [],
            "propagation": {
                "dispatched": 0,
                "dry_run": True,
                "timestamp": "2026-09-05T00:00:00+00:00",
            },
        },
    )

    response = client.post(
        "/api/v1/analysis",
        json={"regulation_text": "Section 1.", "internal_asset_text": "Clause 1."},
    )

    assert response.status_code == 200
    assert list(Path(tmp_path).iterdir()) == []
