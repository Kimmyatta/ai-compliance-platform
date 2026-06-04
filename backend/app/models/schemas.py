from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    privacy_index_available: bool
    fda_guidance_index_available: bool


class DeviceListResponse(BaseModel):
    devices: list[str]


class FdaAuditSummary(BaseModel):
    total_dimensions: int = 0
    completed_dimensions: int = 0
    failed_dimensions: int = 0
    skipped_dimensions: int = 0
    has_errors: bool = False
    all_failed: bool = False


class FdaAuditDimension(BaseModel):
    dimension: str
    status: str
    guidance: str
    risk_level: str
    parsed: dict[str, str]
    audit: str
    error: str = ""
    sources: list[str] = Field(default_factory=list)
    device_evidence: list[dict[str, Any]] = Field(default_factory=list)
    principles: list[str] = Field(default_factory=list)


class FdaAuditResponse(BaseModel):
    filename: str
    summary: FdaAuditSummary
    audits: list[FdaAuditDimension]
    saved_result_path: str | None = None


class FdaAuditJobCreateResponse(BaseModel):
    job_id: str
    status: str
    filename: str


class FdaAuditJobStatusResponse(BaseModel):
    job_id: str
    status: str
    filename: str
    created_at: str
    updated_at: str
    result: FdaAuditResponse | None = None
    error: str | None = None


class FdaAuditJobListResponse(BaseModel):
    jobs: list[FdaAuditJobStatusResponse]


class PrivacyReviewResult(BaseModel):
    regulation: str
    parsed: dict[str, str]
    review: str


class PrivacyReviewResponse(BaseModel):
    filename: str
    reviews: list[PrivacyReviewResult]


class ErrorResponse(BaseModel):
    detail: str
