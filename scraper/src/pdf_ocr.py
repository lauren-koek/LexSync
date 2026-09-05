"""
PDF OCR Pipeline
================
Downloads PDFs from mas_regulations_and_guidance.json and extracts
text using pdfplumber (fast path for native PDFs) or Tesseract OCR
(fallback for scanned PDFs).

Workflow per document:
  1. Download PDF             →  pdfs/<filename>.pdf
  2. Try pdfplumber           →  embedded text (fast)
  3. Fall back to Tesseract   →  render pages via pdf2image → pytesseract
  4. Write full text          →  ocr/<stem>.txt

Usage:
    # Process all docs listed in the JSON file
    python pdf_ocr.py

    # OCR a single local PDF
    python pdf_ocr.py --pdf path/to/file.pdf

    # Point at a different JSON file
    python pdf_ocr.py --json /path/to/other.json

Requirements:
    pip install requests pytesseract pillow pdf2image pdfplumber
    brew install tesseract poppler
"""

import argparse
import json
import logging
import re
import time
from pathlib import Path

import pdfplumber
import pytesseract
import requests
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent
_OUT = _HERE.parent / "output"
JSON_FILE = _OUT / "mas_regulations_and_guidance.json"
PDF_DIR = _OUT / "pdfs"
OCR_DIR = _OUT / "ocr"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
TESSERACT_LANG = "eng"
RENDER_DPI = 300  # higher DPI → better OCR accuracy
NATIVE_TEXT_MIN = 100  # fall back to Tesseract if pdfplumber yields fewer chars


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def _safe_stem(url: str) -> str:
    """Derive a filesystem-safe filename stem from a PDF URL."""
    name = url.split("/")[-1].split("?")[0]
    name = re.sub(r"[^\w.\-]", "_", name)
    return name[:-4] if name.lower().endswith(".pdf") else name


def download_pdf(url: str, dest: Path) -> bool:
    """Download *url* to *dest*. Returns True on success. Skips if already present."""
    if dest.exists():
        logger.info("  [skip]       %s  (already on disk)", dest.name)
        return True
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=60,
            stream=True,
        )
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        logger.info("  [downloaded] %s", dest.name)
        return True
    except requests.RequestException as exc:
        logger.warning("  [FAILED]     %s\n               %s", url, exc)
        return False


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------


def extract_text_native(pdf_path: Path) -> str:
    """Extract embedded text from a native PDF using pdfplumber."""
    pages: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text.strip())
    return "\n\n".join(pages)


def extract_text_ocr(pdf_path: Path) -> str:
    """Extract text from a scanned PDF by rendering pages and running Tesseract."""
    images = convert_from_path(str(pdf_path), dpi=RENDER_DPI)
    logger.info("  OCR-ing %d page(s) via Tesseract …", len(images))
    blocks: list[str] = []
    for i, image in enumerate(images, 1):
        text = pytesseract.image_to_string(image, lang=TESSERACT_LANG)
        blocks.append(f"--- Page {i} ---\n{text.strip()}")
    return "\n\n".join(blocks)


def ocr_pdf(pdf_path: Path, output_dir: Path | None = None) -> str:
    """Extract text from a local PDF.

    Tries pdfplumber first; falls back to Tesseract if the native extraction
    yields fewer than NATIVE_TEXT_MIN characters.

    Writes to output_dir/<stem>.txt when output_dir is provided (for caching).
    Returns the extracted text.
    """
    if output_dir is not None:
        txt_path = output_dir / f"{pdf_path.stem}.txt"
        if txt_path.exists():
            logger.info("  [skip]  %s  (already OCR'd)", txt_path.name)
            return txt_path.read_text(encoding="utf-8")

    logger.info("  Trying native extraction for %s …", pdf_path.name)
    text = extract_text_native(pdf_path)

    if len(text) < NATIVE_TEXT_MIN:
        logger.info("  Native text too short (%d chars), falling back to Tesseract …", len(text))
        text = extract_text_ocr(pdf_path)

    if output_dir is not None:
        txt_path = output_dir / f"{pdf_path.stem}.txt"
        txt_path.write_text(text, encoding="utf-8")
        logger.info("  [saved] %s", txt_path)

    return text


def download_and_ocr(url: str, pdf_dir: Path, ocr_dir: Path) -> str:
    """Download a PDF from *url* and extract its text.

    One-call entry point for the backend pipeline.
    Returns the extracted text.
    """
    pdf_dir.mkdir(parents=True, exist_ok=True)
    ocr_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = pdf_dir / f"{_safe_stem(url)}.pdf"
    if not download_pdf(url, pdf_path):
        raise RuntimeError(f"Failed to download PDF from {url}")

    return ocr_pdf(pdf_path, output_dir=ocr_dir)


# ---------------------------------------------------------------------------
# Orchestration (CLI helpers)
# ---------------------------------------------------------------------------


def _process_json(json_file: Path = JSON_FILE) -> None:
    """Download and OCR every PDF listed in the JSON scraper output."""
    data = json.loads(json_file.read_text(encoding="utf-8"))
    docs = data.get("documents", [])

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    OCR_DIR.mkdir(parents=True, exist_ok=True)

    for i, doc in enumerate(docs, 1):
        url = doc.get("pdf_link")
        title = doc.get("title", "")[:70]

        if not url:
            logger.info("\n[%d/%d] No PDF link — skipping: %s", i, len(docs), title)
            continue

        logger.info("\n[%d/%d] %s", i, len(docs), title)
        download_and_ocr(url, PDF_DIR, OCR_DIR)
        time.sleep(0.5)  # polite pause between downloads


def _process_single(pdf_path: Path) -> None:
    """OCR a single already-downloaded local PDF."""
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("OCR-ing  %s", pdf_path)
    ocr_pdf(pdf_path, output_dir=OCR_DIR)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(
        description="Download MAS PDFs and extract text (pdfplumber + Tesseract fallback).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="Path to a single local PDF. Omit to process all docs in the JSON.",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=JSON_FILE,
        help=f"Path to the scraper JSON output (default: {JSON_FILE}).",
    )
    args = parser.parse_args()

    if args.pdf:
        _process_single(args.pdf)
    else:
        _process_json(args.json)


if __name__ == "__main__":
    main()
