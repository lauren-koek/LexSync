from fastapi import APIRouter, FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.analysis.service import run_analysis
from backend.analysis.uploads import resolve_analysis_text
from backend.analysis.updates import fetch_updates, list_documents
from backend.api.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    DocumentResponse,
    HealthResponse,
    UpdatesRequest,
)

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


app = FastAPI(title="LexSync Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
