# Scraper

Playwright-based scraper for the MAS Regulations and Guidance page.

## Output

Produces `backend/scraper/output/mas_regulations_and_guidance.json` — a JSON object with a `documents` array. Each entry contains:

| Field | Type | Description |
|---|---|---|
| `url` | string | Document page URL |
| `title` | string | Document title |
| `doc_type` | string | e.g. `"Circular"`, `"Guidelines"` |
| `date` | string | Publication date as `"DD Month YYYY"` |
| `topic` | string | Regulatory topic |
| `tags` | array | Free-text tags from MAS |
| `applies_to` | array | Entity types the document applies to |
| `related_items` | array | Related document URLs |
| `pdf_link` | string or null | Direct PDF URL if available |

## CLI

```bash
python -m backend.scraper.src.mas_regulations_scraper
```

No flags required. Output is written to `backend/scraper/output/`.

## Backend API

`pdf_ocr.py` is importable for use in the backend.

### ocr_pdf(pdf_path, output_dir=None) -> str

Extracts text from a local PDF. Tries native text extraction (pdfplumber) first; falls back to Tesseract OCR for scanned/image PDFs. If `output_dir` is provided, writes the text to `<output_dir>/<stem>.txt` as a cache.

### download_and_ocr(url, pdf_dir, ocr_dir) -> str

Downloads a PDF from `url` into `pdf_dir`, then runs `ocr_pdf()` with `ocr_dir` as the cache. Returns the extracted text. Skips download/OCR if cached files already exist.

Example:

```python
from pathlib import Path
from backend.scraper.src.pdf_ocr import download_and_ocr

text = download_and_ocr(
    url="https://www.mas.gov.sg/.../document.pdf",
    pdf_dir=Path("backend/scraper/output/pdfs"),
    ocr_dir=Path("backend/scraper/output/ocr"),
)
```
