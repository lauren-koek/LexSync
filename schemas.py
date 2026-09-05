from typing import Any

from pydantic import BaseModel, Field, field_validator


class AnalysisRequest(BaseModel):
    regulation_text: str = Field(min_length=1)
    internal_asset_text: str = Field(min_length=1)
    regulation_id: str = "Uploaded_Regulation"
    asset_id: str = "Uploaded_Internal_Asset"

    @field_validator("regulation_text", "internal_asset_text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class HealthResponse(BaseModel):
    status: str
    service: str


class LegalImpactResponse(BaseModel):
    is_affected: bool
    impact_score: int
    legal_reasoning: str
    proposed_amended_clause: str
    statutory_citations: list[str]


class ReportEntryResponse(BaseModel):
    regulation: dict[str, Any]
    asset: dict[str, Any]
    similarity_score: float
    analysis: LegalImpactResponse
    redline_diff: str
    analysis_source: str


class PropagationResponse(BaseModel):
    dispatched: int
    dry_run: bool
    timestamp: str


class AnalysisResponse(BaseModel):
    regulation_id: str
    # None for an index-backed analysis (run_analysis_against_index) — matches
    # can span multiple internal documents there, so there's no single asset
    # id to report; each report entry still carries its own asset.doc_id.
    asset_id: str | None = None
    clause_count: int
    match_count: int
    report: list[ReportEntryResponse]
    propagation: PropagationResponse


class InternalDocumentUploadResponse(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int


class UpdatesRequest(BaseModel):
    days: int = Field(ge=1, description="Lookback window in days")


class DocumentResponse(BaseModel):
    id: str | None
    title: str | None
    date: str | None
    doc_type: str | None
    topic: str | None
    tags: list[str]
    applies_to: list[str]
    source_url: str
    pdf_url: str | None
    llm_summary: str | None
    llm_categories: list[str]
    llm_impact_check: str | None
    llm_summary_flagged: bool = False
    llm_summary_check_notes: str | None = None
