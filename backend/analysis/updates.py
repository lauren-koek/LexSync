from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from backend.db import Document, get_session
from backend.llm.processor import process_document
from backend.pipeline import _upsert_document, parse_date
from backend.scraper.src.pdf_ocr import download_and_ocr

logger = logging.getLogger(__name__)

_DEFAULT_JSON = Path("backend/scraper/output/mas_regulations_and_guidance.json")
_DEFAULT_PDF_DIR = Path("backend/scraper/output/pdfs")
_DEFAULT_OCR_DIR = Path("backend/scraper/output/ocr")
_MAX_RESULTS = 50


def fetch_updates(days: int, json_path: Path = _DEFAULT_JSON) -> list[dict]:
    cutoff = date.today() - timedelta(days=days)

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("MAS JSON not found: %s", json_path)
        return []

    docs = [d for d in data.get("documents", []) if _within_window(d, cutoff)]
    docs = docs[:_MAX_RESULTS]

    results: list[dict] = []
    for doc in docs:
        url = doc.get("url", "")

        cached: dict | None = None
        with get_session() as session:
            existing = session.query(Document).filter_by(source_url=url).first()
            if existing and existing.llm_summary:
                cached = _doc_to_dict(existing)

        if cached:
            results.append(cached)
            continue

        ocr_text: str | None = None
        pdf_url = doc.get("pdf_link")
        if pdf_url:
            try:
                ocr_text = download_and_ocr(pdf_url, _DEFAULT_PDF_DIR, _DEFAULT_OCR_DIR)
            except Exception:
                logger.warning("OCR failed for %s", url, exc_info=True)

        processed = None
        if ocr_text:
            try:
                processed = process_document(doc, ocr_text)
            except Exception:
                logger.warning("LLM processing failed for %s", url, exc_info=True)

        with get_session() as session:
            _upsert_document(session, doc, ocr_text, processed)
            saved = session.query(Document).filter_by(source_url=url).first()
            if saved:
                results.append(_doc_to_dict(saved))

    return results


def _within_window(doc: dict, cutoff: date) -> bool:
    parsed = parse_date(doc.get("date", ""))
    return parsed is not None and parsed >= cutoff


def _doc_to_dict(doc: Document) -> dict:
    return {
        "id": str(doc.id),
        "title": doc.title,
        "date": doc.date.isoformat() if doc.date else None,
        "doc_type": doc.doc_type,
        "topic": doc.topic,
        "tags": doc.tags or [],
        "applies_to": doc.applies_to or [],
        "source_url": doc.source_url,
        "pdf_url": doc.pdf_url,
        "llm_summary": doc.llm_summary,
        "llm_categories": doc.llm_categories or [],
        "llm_impact_check": doc.llm_impact_check,
    }
