from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.analysis.service import run_analysis
from backend.analysis.updates import fetch_updates
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
