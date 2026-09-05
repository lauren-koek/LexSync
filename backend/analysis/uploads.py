"""Request-scoped extraction and validation for analysis uploads."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pdfplumber
from fastapi import HTTPException, UploadFile

SUPPORTED_SUFFIXES = {".txt", ".pdf"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _extract_pdf(content: bytes) -> str:
    """Extract text only from a successfully parsed PDF."""
    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Uploaded PDF is malformed or unreadable",
        ) from exc


def extract_upload(upload: UploadFile) -> str:
    """Extract text from an uploaded TXT or PDF without retaining the file."""
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=422, detail="Only .txt and .pdf files are supported")

    content = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds the 10 MB limit")
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=422, detail="Uploaded PDF is malformed or unreadable")
    if suffix == ".txt":
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=422, detail="TXT file must use UTF-8 encoding") from exc
    else:
        text = _extract_pdf(content)

    if not text.strip():
        raise HTTPException(status_code=422, detail="Uploaded file contains no readable text")
    return text


def resolve_analysis_text(
    text: str | None,
    upload: UploadFile | None,
    label: str,
) -> str:
    """Prefer an upload over pasted text and require a non-blank result."""
    resolved = extract_upload(upload) if upload is not None else (text or "")
    if not resolved.strip():
        raise HTTPException(
            status_code=422,
            detail=f"Provide pasted text or a .txt/.pdf file for {label}",
        )
    return resolved
