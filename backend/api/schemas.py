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
    asset_id: str
    clause_count: int
    match_count: int
    report: list[ReportEntryResponse]
    propagation: PropagationResponse


class UpdatesRequest(BaseModel):
    days: int = Field(ge=1, description="Lookback window in days")
    refresh: bool = Field(
        default=False,
        description="Re-pull metadata and regenerate LLM output for saved documents",
    )


class DocumentResponse(BaseModel):
    id: str | None
    title: str | None
    date: str | None
    effective_date: str | None = None
    doc_type: str | None
    topic: str | None
    tags: list[str]
    applies_to: list[str]
    issued_pursuant_to_text: str | None = None
    issued_pursuant_to: list[dict[str, Any]] = []
    source_url: str
    pdf_url: str | None
    llm_summary: str | None
    llm_categories: list[str]
    llm_impact_check: str | None
    suggestion_count: int = 0


class InternalDocumentSummary(BaseModel):
    id: str
    title: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    chunk_count: int
    created_at: str | None
    updated_at: str | None
    deduplicated: bool = False


class InternalChunkResponse(BaseModel):
    id: str
    clause_reference: str
    content: str
    review_status: str
    review_reason: str | None = None
    last_reviewed_at: str | None = None


class SuggestionResponse(BaseModel):
    id: str
    regulatory_document_id: str
    internal_document_id: str
    internal_chunk_id: str
    regulation_clause_reference: str
    regulation_content: str
    similarity_score: float
    is_affected: bool
    impact_score: int
    legal_reasoning: str
    proposed_amended_clause: str
    statutory_citations: list[str]
    redline_diff: str
    analysis_source: str
    status: str


class InternalDocumentDetail(InternalDocumentSummary):
    chunks: list[InternalChunkResponse]
    suggestions: list[SuggestionResponse]


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value.strip()


class SuggestionStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in {"pending", "accepted", "dismissed"}:
            raise ValueError("invalid suggestion status")
        return value
