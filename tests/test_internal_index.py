from types import SimpleNamespace

from internal_index import group_search_rows


def test_group_search_rows_collapses_chunks_and_limits_excerpts():
    doc_a = SimpleNamespace(id="a", title="Incident Policy", filename="incident.pdf")
    doc_b = SimpleNamespace(id="b", title="Vendor Terms", filename="vendor.pdf")
    rows = [
        (SimpleNamespace(id="a1", document=doc_a, clause_reference="Clause 1", content="breach"), 0.05),
        (SimpleNamespace(id="a2", document=doc_a, clause_reference="Clause 2", content="notice"), 0.10),
        (SimpleNamespace(id="a3", document=doc_a, clause_reference="Clause 3", content="extra"), 0.15),
        (SimpleNamespace(id="b1", document=doc_b, clause_reference="Clause 4", content="vendor"), 0.20),
    ]

    results = group_search_rows(rows, limit=2, excerpts_per_document=2, threshold=0.5)

    assert [item["title"] for item in results] == ["Incident Policy", "Vendor Terms"]
    assert [item["score"] for item in results] == [0.95, 0.8]
    assert len(results[0]["excerpts"]) == 2
