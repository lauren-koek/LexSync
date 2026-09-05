from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from backend.analysis import uploads


def make_upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(content))


def test_resolve_analysis_text_decodes_txt_and_takes_precedence():
    upload = make_upload("regulation.txt", b"Section 12A. Keep records.")

    result = uploads.resolve_analysis_text("pasted fallback", upload, "regulation")

    assert result == "Section 12A. Keep records."


def test_extract_upload_delegates_pdf_to_ingest(monkeypatch):
    upload = make_upload("regulation.pdf", b"%PDF-test")
    observed = {"content": None}

    def fake_extract(content):
        observed["content"] = content
        return "Extracted PDF text"

    monkeypatch.setattr(uploads, "_extract_pdf", fake_extract)

    assert uploads.extract_upload(upload) == "Extracted PDF text"
    assert observed["content"] == b"%PDF-test"


@pytest.mark.parametrize("filename", ["notes.docx", "regulation.exe"])
def test_extract_upload_rejects_unsupported_files(filename):
    with pytest.raises(HTTPException) as error:
        uploads.extract_upload(make_upload(filename, b"content"))

    assert error.value.status_code == 422


def test_resolve_analysis_text_rejects_missing_or_blank_content():
    with pytest.raises(HTTPException) as error:
        uploads.resolve_analysis_text("   ", None, "internal asset")

    assert error.value.status_code == 422
    assert "internal asset" in error.value.detail


def test_extract_upload_rejects_malformed_pdf():
    with pytest.raises(HTTPException) as error:
        uploads.extract_upload(make_upload("broken.pdf", b"%PDF-not-really-a-document"))

    assert error.value.status_code == 422


def test_extract_upload_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr(uploads, "MAX_UPLOAD_BYTES", 4)

    with pytest.raises(HTTPException) as error:
        uploads.extract_upload(make_upload("large.txt", b"12345"))

    assert error.value.status_code == 413
