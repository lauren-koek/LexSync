import tempfile
from pathlib import Path

from fastapi import APIRouter, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.analysis import ingest, internal_index
from backend.analysis.service import run_analysis
from backend.analysis.updates import fetch_updates
from backend.api.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    DocumentResponse,
    HealthResponse,
    InternalDocumentUploadResponse,
    UpdatesRequest,
)

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    return {"status": "ok", "service": "lexsync-backend"}


@router.post("/analysis", response_model=AnalysisResponse)
def analysis(request: AnalysisRequest) -> dict:
    return run_analysis(**request.model_dump())


@router.post("/internal-documents", response_model=InternalDocumentUploadResponse)
async def upload_internal_document(file: UploadFile = File(...)) -> dict:
    """Ingest an uploaded internal document end-to-end: extract its text,
    split it into citation-aware clauses, embed each clause, and persist
    them in the pgvector-backed internal-document index — this is the
    "upload a document" entry point for backend/analysis/internal_index.py,
    which previously could only be populated by calling build_index()
    directly (e.g. from the CLI ingestion path or a test).
    """
    suffix = Path(file.filename or "").suffix or ".txt"
    raw_bytes = await file.read()

    # ingest.extract_text() reads by filesystem path (pdfplumber/docling
    # both require one), so the upload — which FastAPI hands us as raw
    # bytes — has to be written to a real file first. The temp file's
    # suffix has to match the original filename's so extract_text() picks
    # the right extraction engine (PDF vs. plain text) instead of always
    # falling back to a plain-text read.
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp_file:
        tmp_file.write(raw_bytes)
        tmp_file.flush()
        text = ingest.extract_text(Path(tmp_file.name))

    if not text.strip():
        raise HTTPException(
            status_code=422, detail="No extractable text found in the uploaded file"
        )

    # The filename (minus extension) becomes doc_id, which build_index()
    # uses to replace old chunks on re-upload — so uploading "Vendor_DPA.pdf"
    # twice updates the existing entry instead of accumulating duplicates.
    doc_id = Path(file.filename or "uploaded_document").stem
    chunks = ingest.chunk_legal_document(text, "INTERNAL_ASSET", doc_id)
    chunk_count = internal_index.build_index(chunks)

    return {
        "doc_id": doc_id,
        "filename": file.filename or "",
        "chunk_count": chunk_count,
    }


@router.post("/updates", response_model=list[DocumentResponse])
def updates(request: UpdatesRequest) -> list[dict]:
    return fetch_updates(request.days)


app = FastAPI(title="LexSync Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
