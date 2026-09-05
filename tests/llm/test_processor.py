from unittest.mock import patch

import pytest

from backend.llm.processor import process_document


def test_process_document_retries_malformed_json_and_returns_parsed_result():
    malformed = (
        '{ "summary": "On 04 September 2026, the Monetary Authority of Singapore '
        "issued Notice 656"
    )
    corrected = """{
        "summary": "MAS issued Notice 656 on 04 September 2026.",
        "categories": ["Financial Services"],
        "impact_check": "Artefact types to review: counterparty exposure policies"
    }"""

    with patch("backend.llm.processor.chat", side_effect=[malformed, corrected]):
        result = process_document(
            {"title": "Notice 656", "date": "04 September 2026"},
            "Source document text",
        )

    assert result.llm_summary == "MAS issued Notice 656 on 04 September 2026."
    assert result.llm_categories == ["Financial Services"]
    assert result.llm_impact_check == (
        "Artefact types to review: counterparty exposure policies"
    )


def test_process_document_does_not_return_raw_json_when_retry_is_malformed():
    malformed = '{"summary": "Truncated response'

    with (
        patch("backend.llm.processor.chat", side_effect=[malformed, malformed]),
        pytest.raises(ValueError, match="valid JSON"),
    ):
        process_document({"title": "Notice 656"}, "Source document text")
