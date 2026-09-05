import argparse
import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

from backend.analysis.suggestions import analyze_regulatory_document
from backend.db import Document, create_tables, get_session
from backend.llm.processor import process_document
from backend.scraper.src.pdf_ocr import download_and_ocr

logger = logging.getLogger(__name__)

_DEFAULT_JSON = Path("backend/scraper/output/mas_regulations_and_guidance.json")
_DEFAULT_PDF_DIR = Path("backend/scraper/output/pdfs")
_DEFAULT_OCR_DIR = Path("backend/scraper/output/ocr")

_DATE_FORMAT = "%d %B %Y"


def _pdf_url(doc: dict) -> str | None:
    """Return the first PDF URL from either scraper output format."""
    if doc.get("pdf_link"):
        return doc["pdf_link"]
    pdf_links = doc.get("pdf_links", [])
    return pdf_links[0] if pdf_links else None


def parse_date(date_str: str) -> date | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), _DATE_FORMAT).date()
    except ValueError:
        logger.warning("Could not parse date: %r", date_str)
        return None


def _upsert_document(session, doc: dict, ocr_text: str | None, processed) -> Document:
    source_url = doc.get("url", "")
    existing = session.query(Document).filter_by(source_url=source_url).first()

    parsed_date = parse_date(doc.get("date", ""))
    parsed_effective_date = parse_date(doc.get("effective_date", ""))
    now = datetime.now(tz=UTC)

    if existing is None:
        record = Document(
            source_url=source_url,
            title=doc.get("title"),
            doc_type=doc.get("doc_type"),
            date=parsed_date,
            effective_date=parsed_effective_date,
            topic=doc.get("topic"),
            tags=doc.get("tags", []),
            applies_to=doc.get("applies_to", []),
            issued_pursuant_to_text=doc.get("issued_pursuant_to_text"),
            issued_pursuant_to=doc.get("issued_pursuant_to", []),
            related_items=doc.get("related_items", []),
            pdf_url=_pdf_url(doc),
            ocr_text=ocr_text,
            llm_summary=processed.llm_summary if processed else None,
            llm_categories=processed.llm_categories if processed else None,
            llm_impact_check=processed.llm_impact_check if processed else None,
            scraped_at=now,
            processed_at=now if processed else None,
        )
        session.add(record)
        saved = record
    else:
        existing.title = doc.get("title")
        existing.doc_type = doc.get("doc_type")
        existing.date = parsed_date
        existing.effective_date = parsed_effective_date
        existing.topic = doc.get("topic")
        existing.tags = doc.get("tags", [])
        existing.applies_to = doc.get("applies_to", [])
        existing.issued_pursuant_to_text = doc.get("issued_pursuant_to_text")
        existing.issued_pursuant_to = doc.get("issued_pursuant_to", [])
        existing.related_items = doc.get("related_items", [])
        existing.pdf_url = _pdf_url(doc)
        if ocr_text is not None:
            existing.ocr_text = ocr_text
        if processed is not None:
            existing.llm_summary = processed.llm_summary
            existing.llm_categories = processed.llm_categories
            existing.llm_impact_check = processed.llm_impact_check
            existing.processed_at = now
        existing.scraped_at = now
        saved = existing
    return saved


def _generate_suggestions_safely(document_id: UUID | str) -> None:
    """Analyze a saved regulation without endangering its ingestion commit."""
    try:
        with get_session() as session:
            analyze_regulatory_document(UUID(str(document_id)), session)
    except Exception:
        logger.warning(
            "Suggestion generation failed for regulatory document %s",
            document_id,
            exc_info=True,
        )


def run(
    json_path: Path,
    pdf_dir: Path,
    ocr_dir: Path,
    limit: int | None,
    skip_ocr: bool,
    skip_llm: bool,
) -> None:
    create_tables()

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.error("Scraper JSON not found: %s", json_path)
        return

    docs = data.get("documents", [])
    if limit is not None:
        docs = docs[:limit]

    total = len(docs)
    logger.info("Processing %d document(s)", total)

    for i, doc in enumerate(docs, 1):
        title = doc.get("title", doc.get("url", f"doc #{i}"))
        logger.info("[%d/%d] %s", i, total, title)

        try:
            ocr_text: str | None = None
            if not skip_ocr:
                pdf_url = _pdf_url(doc)
                if pdf_url:
                    ocr_text = download_and_ocr(pdf_url, pdf_dir, ocr_dir)
                else:
                    logger.warning("No pdf_link for: %s", title)

            processed = None
            if not skip_llm and ocr_text:
                processed = process_document(doc, ocr_text)

            with get_session() as session:
                saved = _upsert_document(session, doc, ocr_text, processed)
                session.flush()
                saved_id = saved.id

            if ocr_text and ocr_text.strip():
                _generate_suggestions_safely(saved_id)

            logger.info("[%d/%d] Saved: %s", i, total, title)

        except Exception:
            logger.warning("Failed to process document: %s", title, exc_info=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="LexSync pipeline: OCR + LLM + DB upsert")
    parser.add_argument("--json", type=Path, default=_DEFAULT_JSON)
    parser.add_argument("--pdf-dir", type=Path, default=_DEFAULT_PDF_DIR)
    parser.add_argument("--ocr-dir", type=Path, default=_DEFAULT_OCR_DIR)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-ocr", action="store_true")
    parser.add_argument("--skip-llm", action="store_true")
    args = parser.parse_args()

    run(
        json_path=args.json,
        pdf_dir=args.pdf_dir,
        ocr_dir=args.ocr_dir,
        limit=args.limit,
        skip_ocr=args.skip_ocr,
        skip_llm=args.skip_llm,
    )


if __name__ == "__main__":
    main()
