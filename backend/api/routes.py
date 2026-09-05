from uuid import UUID

from fastapi import (
    APIRouter,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware

from backend.analysis.internal_documents import (
    InternalDocumentValidationError,
    delete_internal_document,
    ingest_pdf,
)
from backend.analysis.service import run_analysis
from backend.analysis.suggestions import (
    analyze_regulatory_document,
    reanalyze_internal_document,
    set_suggestion_status,
)
from backend.analysis.updates import fetch_updates, list_documents
from backend.analysis.uploads import resolve_analysis_text
from backend.api.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    DocumentResponse,
    HealthResponse,
    InternalDocumentDetail,
    InternalDocumentSummary,
    SemanticSearchRequest,
    SuggestionResponse,
    SuggestionStatusRequest,
    UpdatesRequest,
)
from backend.db import DocumentSuggestion, InternalDocument, get_session
from backend.storage import ObjectStorageError, get_object_storage
from internal_index import semantic_search

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    return {"status": "ok", "service": "lexsync-backend"}


@router.post("/analysis", response_model=AnalysisResponse)
def analysis(request: AnalysisRequest) -> dict:
    return run_analysis(**request.model_dump())


@router.post("/analysis/upload", response_model=AnalysisResponse)
def analysis_upload(
    regulation_text: str | None = Form(default=None),
    internal_asset_text: str | None = Form(default=None),
    regulation_file: UploadFile | None = File(default=None),
    internal_asset_file: UploadFile | None = File(default=None),
    regulation_id: str = Form(default="Uploaded_Regulation"),
    asset_id: str = Form(default="Uploaded_Internal_Asset"),
) -> dict:
    return run_analysis(
        regulation_text=resolve_analysis_text(
            regulation_text, regulation_file, "regulation"
        ),
        internal_asset_text=resolve_analysis_text(
            internal_asset_text, internal_asset_file, "internal asset"
        ),
        regulation_id=regulation_id,
        asset_id=asset_id,
    )


@router.post("/updates", response_model=list[DocumentResponse])
def updates(request: UpdatesRequest) -> list[dict]:
    return fetch_updates(request.days, refresh=request.refresh)


@router.get("/documents", response_model=list[DocumentResponse])
def documents() -> list[dict]:
    return list_documents()


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def _internal_summary(document: InternalDocument, *, deduplicated: bool = False) -> dict:
    return {
        "id": str(document.id),
        "title": document.title,
        "filename": document.filename,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "status": document.status,
        "chunk_count": document.chunk_count,
        "created_at": _iso(document.created_at),
        "updated_at": _iso(document.updated_at),
        "deduplicated": deduplicated,
    }


def _suggestion_dict(suggestion: DocumentSuggestion) -> dict:
    return {
        "id": str(suggestion.id),
        "regulatory_document_id": str(suggestion.regulatory_document_id),
        "internal_document_id": str(suggestion.internal_document_id),
        "internal_chunk_id": str(suggestion.internal_chunk_id),
        "regulation_clause_reference": suggestion.regulation_clause_reference,
        "regulation_content": suggestion.regulation_content,
        "similarity_score": suggestion.similarity_score,
        "is_affected": suggestion.is_affected,
        "impact_score": suggestion.impact_score,
        "legal_reasoning": suggestion.legal_reasoning,
        "proposed_amended_clause": suggestion.proposed_amended_clause,
        "statutory_citations": suggestion.statutory_citations or [],
        "redline_diff": suggestion.redline_diff,
        "analysis_source": suggestion.analysis_source,
        "status": suggestion.status,
    }


@router.post("/internal-documents", response_model=InternalDocumentSummary, status_code=201)
def upload_internal_document(
    response: Response,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
) -> dict:
    content = file.file.read(10 * 1024 * 1024 + 1)
    try:
        storage = get_object_storage()
        with get_session() as session:
            result = ingest_pdf(
                filename=file.filename or "document.pdf",
                content_type=file.content_type or "",
                content=content,
                title=title,
                storage=storage,
                session=session,
            )
            payload = _internal_summary(
                result.document, deduplicated=result.deduplicated
            )
        if result.deduplicated:
            response.status_code = 200
        return payload
    except InternalDocumentValidationError as exc:
        status = 413 if "10 MB" in str(exc) else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except ObjectStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/internal-documents", response_model=list[InternalDocumentSummary])
def internal_documents(
    q: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict]:
    try:
        with get_session() as session:
            query = session.query(InternalDocument)
            if q and q.strip():
                term = f"%{q.strip()}%"
                query = query.filter(
                    InternalDocument.title.ilike(term)
                    | InternalDocument.filename.ilike(term)
                )
            rows = query.order_by(InternalDocument.created_at.desc()).offset(offset).limit(limit).all()
            return [_internal_summary(row) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Unable to list internal documents") from exc


@router.post("/internal-documents/search")
def search_internal_documents(request: SemanticSearchRequest) -> list[dict]:
    return semantic_search(request.query, limit=request.limit)


@router.get("/internal-documents/{document_id}", response_model=InternalDocumentDetail)
def internal_document_detail(document_id: UUID) -> dict:
    with get_session() as session:
        document = session.get(InternalDocument, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Internal document not found")
        payload = _internal_summary(document)
        payload["chunks"] = [
            {
                "id": str(chunk.id),
                "clause_reference": chunk.clause_reference,
                "content": chunk.content,
            }
            for chunk in document.chunks
        ]
        payload["suggestions"] = [_suggestion_dict(item) for item in document.suggestions]
        return payload


@router.get("/internal-documents/{document_id}/pdf-url")
def internal_document_pdf_url(document_id: UUID) -> dict[str, str]:
    with get_session() as session:
        document = session.get(InternalDocument, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Internal document not found")
        object_key = document.object_key
    try:
        return {"url": get_object_storage().presigned_get_url(object_key, 900)}
    except ObjectStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.delete("/internal-documents/{document_id}", status_code=204)
def remove_internal_document(document_id: UUID) -> Response:
    with get_session() as session:
        try:
            delete_internal_document(document_id, get_object_storage(), session)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ObjectStorageError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post("/internal-documents/{document_id}/reanalyze")
def reanalyze_internal(document_id: UUID) -> dict[str, int]:
    with get_session() as session:
        if session.get(InternalDocument, document_id) is None:
            raise HTTPException(status_code=404, detail="Internal document not found")
        return {"suggestion_count": reanalyze_internal_document(document_id, session)}


@router.post("/documents/{document_id}/reanalyze")
def reanalyze_regulatory(document_id: UUID) -> dict[str, int]:
    with get_session() as session:
        try:
            count = analyze_regulatory_document(document_id, session)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"suggestion_count": count}


@router.get("/documents/{document_id}/suggestions", response_model=list[SuggestionResponse])
def regulatory_suggestions(document_id: UUID) -> list[dict]:
    with get_session() as session:
        rows = session.query(DocumentSuggestion).filter_by(
            regulatory_document_id=document_id
        ).all()
        return [_suggestion_dict(row) for row in rows]


@router.patch("/document-suggestions/{suggestion_id}", response_model=SuggestionResponse)
def update_suggestion(suggestion_id: UUID, request: SuggestionStatusRequest) -> dict:
    with get_session() as session:
        try:
            suggestion = set_suggestion_status(suggestion_id, request.status, session)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _suggestion_dict(suggestion)


app = FastAPI(title="LexSync Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
