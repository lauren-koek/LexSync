"""
ingest.py — Component 1: Scraper / Document Ingestion

Turns raw regulatory updates and internal legal documents (PDF, HTML, or .txt)
into a flat list of structured, retrieval-ready "clauses". This is the entry
point of the pipeline: everything downstream (vector search, LLM impact
analysis, notification) consumes the `ingested_data.json` file this produces.

Design notes (why it's built this way):
- `docling` (IBM's layout-aware PDF parser) is powerful but heavy: it pulls in
  torch and large models, which is a real risk for a live demo (slow/flaky
  install, cold-start latency). We treat it as a *bonus* engine and default to
  `pdfplumber`, which is lightweight and fast. If neither is installed, we
  fall back to reading the file as plain text so the pipeline never crashes.
- If no input files exist yet (e.g. first run, or offline demo), we seed the
  pipeline with realistic hardcoded sample data so the whole system is
  demoable end-to-end with zero setup.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

SOURCE_DIR = Path("sample_docs")
OUTPUT_PATH = Path("ingested_data.json")

SourceType = Literal["REGULATION", "INTERNAL_ASSET"]

# Word count target per chunk and overlap between consecutive chunks, so a
# clause that spans a chunk boundary still has full context on both sides.
TARGET_CHUNK_WORDS = 400
OVERLAP_WORDS = 50

# Matches legal section/clause headers like "Section 12A.", "Clause 4.1",
# "Article 3", "§ 5.2" — used as preferred split points so we don't cut a
# clause in half.
CLAUSE_BOUNDARY_RE = re.compile(
    r"(?m)^\s*(Section\s+\d+[A-Za-z]?\.?|Clause\s+\d+(\.\d+)*\.?|Article\s+\d+\.?|§\s?\d+(\.\d+)*)",
)


@dataclass
class Clause:
    id: str
    doc_id: str
    source_type: SourceType
    title: str
    clause_reference: str
    content: str


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text(path: Path) -> str:
    """Extract raw text from a file, trying the best available engine first.

    docling -> pdfplumber -> plain-text read. Each stage is wrapped so a
    missing dependency or a malformed file degrades gracefully instead of
    killing the whole ingestion run.
    """
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        try:
            from docling.document_converter import DocumentConverter  # type: ignore

            converter = DocumentConverter()
            result = converter.convert(str(path))
            return result.document.export_to_markdown()
        except Exception:
            pass  # docling not installed or failed — fall through

        try:
            import pdfplumber  # type: ignore

            with pdfplumber.open(str(path)) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception:
            pass  # pdfplumber not installed or failed — fall through to plain text

    # HTML / TXT / fallback: read as plain text.
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_legal_document(text: str, source_type: str, doc_id: str) -> list[dict]:
    """Split a legal document into retrieval-sized, citation-aware chunks.

    Strategy:
    1. Prefer splitting on clause/section boundaries (Section 1., Clause 4.1,
       Article 3, § 5.2) so each chunk stays a coherent legal unit and keeps
       its own citation.
    2. If a resulting section is much larger than the target size, further
       split it by word count with overlap, so retrieval doesn't miss
       content buried in an oversized section.
    """
    text = text.strip()
    if not text:
        return []

    boundaries = list(CLAUSE_BOUNDARY_RE.finditer(text))

    if boundaries:
        segments: list[tuple[str, str]] = []  # (clause_reference, text)
        for i, match in enumerate(boundaries):
            start = match.start()
            end = boundaries[i + 1].start() if i + 1 < len(boundaries) else len(text)
            clause_ref = match.group(1).strip().rstrip(".")
            segments.append((clause_ref, text[start:end].strip()))
    else:
        segments = [("General", text)]

    chunks: list[dict] = []
    for clause_ref, segment_text in segments:
        words = segment_text.split()
        if len(words) <= TARGET_CHUNK_WORDS * 1.5:
            chunks.append(_make_chunk(doc_id, source_type, clause_ref, segment_text))
            continue

        # Oversized section: slide a window over it with overlap.
        step = TARGET_CHUNK_WORDS - OVERLAP_WORDS
        for start in range(0, len(words), step):
            window = words[start:start + TARGET_CHUNK_WORDS]
            if not window:
                continue
            sub_ref = f"{clause_ref} (part {start // step + 1})"
            chunks.append(_make_chunk(doc_id, source_type, sub_ref, " ".join(window)))
            if start + TARGET_CHUNK_WORDS >= len(words):
                break

    return chunks


def _make_chunk(doc_id: str, source_type: str, clause_reference: str, content: str) -> dict:
    title = f"{doc_id} — {clause_reference}"
    clause = Clause(
        id=str(uuid.uuid4()),
        doc_id=doc_id,
        source_type=source_type,  # type: ignore[arg-type]
        title=title,
        clause_reference=clause_reference,
        content=content,
    )
    return asdict(clause)


# ---------------------------------------------------------------------------
# Hardcoded sample data (used when sample_docs/ is empty)
# ---------------------------------------------------------------------------

SAMPLE_REGULATION = """Section 12A. Mandatory AI Automated Decision Audit Logs.
Audit logs generated in connection with any automated decision-making system
that processes personal data must be retained for a period of seven (7) years
from the date of creation (previously three (3) years under the prior
regime). Where an automated decision-making system is involved in a critical
safety breach, the organisation must notify affected data subjects within
twenty-four (24) hours of discovering the breach.

Section 12B. Scope.
This Section applies to any organisation that deploys an automated
decision-making system which processes the personal data of individuals in
Singapore, regardless of where the system is hosted."""

SAMPLE_INTERNAL_ASSET = """Clause 8. Data Retention & Security.
The Vendor shall retain processing logs for a minimum of thirty-six (36)
months from the date of creation. The Vendor shall notify the Company of any
material data breach within seventy-two (72) hours of discovery.

Clause 9. Audit Rights.
The Company reserves the right to audit the Vendor's data handling practices
upon thirty (30) days' written notice."""


def load_documents() -> list[tuple[str, SourceType, str]]:
    """Return a list of (doc_id, source_type, raw_text) tuples to ingest.

    Reads every file under sample_docs/{regulations,internal}/ if present;
    otherwise falls back to hardcoded high-quality sample data so the
    pipeline is always demoable.
    """
    documents: list[tuple[str, SourceType, str]] = []

    reg_dir = SOURCE_DIR / "regulations"
    internal_dir = SOURCE_DIR / "internal"

    if reg_dir.exists():
        for path in sorted(reg_dir.glob("*")):
            if path.is_file():
                documents.append((path.stem, "REGULATION", extract_text(path)))

    if internal_dir.exists():
        for path in sorted(internal_dir.glob("*")):
            if path.is_file():
                documents.append((path.stem, "INTERNAL_ASSET", extract_text(path)))

    if not documents:
        documents.append(("PDPA_2026_Revision", "REGULATION", SAMPLE_REGULATION))
        documents.append(("Vendor_DPA_Template", "INTERNAL_ASSET", SAMPLE_INTERNAL_ASSET))

    return documents


def run_ingestion() -> list[dict]:
    all_chunks: list[dict] = []
    for doc_id, source_type, text in load_documents():
        all_chunks.extend(chunk_legal_document(text, source_type, doc_id))

    OUTPUT_PATH.write_text(json.dumps(all_chunks, indent=2), encoding="utf-8")
    return all_chunks


if __name__ == "__main__":
    chunks = run_ingestion()
    reg_count = sum(1 for c in chunks if c["source_type"] == "REGULATION")
    asset_count = sum(1 for c in chunks if c["source_type"] == "INTERNAL_ASSET")
    print(f"Ingested {len(chunks)} clauses ({reg_count} regulation, {asset_count} internal asset).")
    print(f"Wrote {OUTPUT_PATH.resolve()}")
