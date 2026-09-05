from fastapi import APIRouter, FastAPI

from backend.analysis.service import run_analysis
from backend.api.schemas import AnalysisRequest, AnalysisResponse, HealthResponse

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    return {"status": "ok", "service": "lexsync-backend"}


@router.post("/analysis", response_model=AnalysisResponse)
def analysis(request: AnalysisRequest) -> dict:
    return run_analysis(**request.model_dump())


app = FastAPI(title="LexSync Backend", version="1.0.0")
app.include_router(router)
