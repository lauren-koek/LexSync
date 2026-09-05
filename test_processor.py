import json
from unittest.mock import patch

from backend.llm.processor import process_document

DOC = {"title": "Test Circular", "date": "2026-09-05", "doc_type": "Circular", "url": "https://x"}
OCR_TEXT = "Section 12A. Audit logs must be retained for seven (7) years from creation."


def _chat_returning(summary: str):
    return json.dumps(
        {"summary": summary, "categories": ["General"], "impact_check": "None."}
    )


def test_process_document_flags_fabricated_number():
    fabricated_summary = "Audit logs must now be retained for 3 years."

    with patch("backend.llm.processor.chat", return_value=_chat_returning(fabricated_summary)):
        result = process_document(DOC, OCR_TEXT)

    assert result.hallucination_flag is True
    assert "3" in result.hallucination_notes


def test_process_document_does_not_flag_accurate_summary():
    accurate_summary = "Audit logs must be retained for 7 years from creation."

    with patch("backend.llm.processor.chat", return_value=_chat_returning(accurate_summary)):
        result = process_document(DOC, OCR_TEXT)

    assert result.hallucination_flag is False
    assert result.hallucination_notes == "Summary numbers and vocabulary are grounded in the source text."
