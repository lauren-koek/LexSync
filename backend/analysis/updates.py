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


def _run_scraper(days: int, output_path: Path) -> None:
    """Run the Playwright MAS scraper and write results to output_path."""
    from playwright.sync_api import sync_playwright

    from backend.scraper.src.mas_regulations_scraper import (
        USER_AGENT,
        enrich_with_details,
        fetch_listing_html,
        filter_last_n_days,
        parse_listing,
        save_records,
    )

    logger.info("Running MAS scraper for last %d day(s)…", days)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            user_agent=USER_AGENT,
            ignore_https_errors=True,
        )
        listing_html = fetch_listing_html(page)
        records = parse_listing(listing_html)
        logger.info("Scraper found %d documents in listing", len(records))
        if days > 0:
            records = filter_last_n_days(records, days)
            logger.info("Filtered to last %d day(s): %d documents", days, len(records))
        enrich_with_details(page, records)
        browser.close()

    save_records(records, path=str(output_path))
    logger.info("Scraper saved %d records to %s", len(records), output_path)


def _normalise_doc(doc: dict) -> dict:
    """Ensure doc has a pdf_link field (scraper writes pdf_links list)."""
    if "pdf_link" not in doc:
        links = doc.get("pdf_links") or []
        doc = {**doc, "pdf_link": links[0] if links else None}
    return doc


def fetch_updates(
    days: int, json_path: Path = _DEFAULT_JSON, refresh: bool = False
) -> list[dict]:
    """Re-scrape MAS and return the matching documents.

    By default, documents already saved with an LLM summary are served from the
    database and their expensive OCR/LLM steps are skipped. When ``refresh`` is
    True, those documents' scraped metadata (including ``issued_pursuant_to``,
    tags, and ``applies_to``) is re-pulled and overwritten, while the cached
    OCR text and LLM output are preserved (no re-processing).
    """
    _run_scraper(days, json_path)

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("MAS JSON not found after scrape: %s", json_path)
        return []

    cutoff = date.today() - timedelta(days=days)
    docs = [_normalise_doc(d) for d in data.get("documents", []) if _within_window(d, cutoff)]
    docs = docs[:_MAX_RESULTS]

    results: list[dict] = []
    for doc in docs:
        url = doc.get("url", "")

        already_processed = False
        cached: dict | None = None
        with get_session() as session:
            existing = session.query(Document).filter_by(source_url=url).first()
            if existing and existing.llm_summary:
                already_processed = True
                cached = _doc_to_dict(existing)

        # Serve from cache unless the caller explicitly asked to refresh.
        if already_processed and not refresh:
            results.append(cached)
            continue

        # For a refresh of an already-processed doc, re-upsert scraped metadata
        # only — leave OCR/LLM as None so the existing cached values are kept.
        ocr_text: str | None = None
        processed = None
        if not already_processed:
            pdf_url = doc.get("pdf_link")
            if pdf_url:
                try:
                    ocr_text = download_and_ocr(pdf_url, _DEFAULT_PDF_DIR, _DEFAULT_OCR_DIR)
                except Exception:
                    logger.warning("OCR failed for %s", url, exc_info=True)

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


def list_documents(limit: int = _MAX_RESULTS) -> list[dict]:
    """Return saved documents in newest-first order."""
    with get_session() as session:
        docs = (
            session.query(Document)
            .order_by(
                Document.date.desc().nullslast(),
                Document.created_at.desc(),
            )
            .limit(limit)
            .all()
        )
        return [_doc_to_dict(doc) for doc in docs]


def _within_window(doc: dict, cutoff: date) -> bool:
    parsed = parse_date(doc.get("date", ""))
    return parsed is not None and parsed >= cutoff


def _doc_to_dict(doc: Document) -> dict:
    return {
        "id": str(doc.id),
        "title": doc.title,
        "date": doc.date.isoformat() if doc.date else None,
        "effective_date": doc.effective_date.isoformat() if doc.effective_date else None,
        "doc_type": doc.doc_type,
        "topic": doc.topic,
        "tags": doc.tags or [],
        "applies_to": doc.applies_to or [],
        "issued_pursuant_to_text": doc.issued_pursuant_to_text,
        "issued_pursuant_to": doc.issued_pursuant_to or [],
        "source_url": doc.source_url,
        "pdf_url": doc.pdf_url,
        "llm_summary": doc.llm_summary,
        "llm_categories": doc.llm_categories or [],
        "llm_impact_check": doc.llm_impact_check,
    }
