from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    privacy_index_available: bool
    fda_guidance_index_available: bool
    afrisafe_frameworks_index_available: bool


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
    current_dimension: str | None = None
    current_dimension_index: int = 0
    total_dimensions: int = 0
    completed_dimensions: int = 0
    progress_percent: int = 0
    message: str | None = None
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


class AiSafetyModel(BaseModel):
    id: str
    label: str


class AiSafetyScenario(BaseModel):
    scenario_id: str
    title: str
    country: str
    healthcare_context: str = ""
    scenario_description: str
    expected_risk_categories: list[str]
    risk_severity: str = "Unknown"
    severity: str
    explanation: str


class AiSafetyScenarioListResponse(BaseModel):
    scenarios: list[AiSafetyScenario]


class AiSafetyModelsResponse(BaseModel):
    models: list[AiSafetyModel]


class AiSafetyFramework(BaseModel):
    name: str
    source_year: str | None = None
    review_focus: list[str] = Field(default_factory=list)
    risk_categories: list[str] = Field(default_factory=list)


class AiSafetyFrameworksResponse(BaseModel):
    frameworks: list[AiSafetyFramework]


class AiSafetyFrameworkDocumentListResponse(BaseModel):
    documents: list[str]


class AiSafetyFrameworkUploadResponse(BaseModel):
    filename: str
    path: str
    message: str


class AiSafetyTextRequest(BaseModel):
    title: str = "Uploaded AI healthcare deployment document"
    country: str = ""
    text: str
    expected_risk_categories: list[str] = Field(default_factory=list)
    model: str = "llama-3.3-70b-versatile"


class AiSafetyFrameworkGuidanceRequest(BaseModel):
    model: str = "llama-3.3-70b-versatile"
    detected_risks: list[dict[str, Any]] = Field(default_factory=list)
    missed_risks: list[str] = Field(default_factory=list)
    k: int = 6


class AiSafetyRescoredReview(BaseModel):
    review_id: str
    scenario_id: str
    title: str
    country: str = ""
    model: str
    coverage_score: float
    missed_risks: list[str] = Field(default_factory=list)
    path: str


class AiSafetyRescoredReviewListResponse(BaseModel):
    reviews: list[AiSafetyRescoredReview]


class AiSafetyRescoredGuidanceRequest(BaseModel):
    source_model: str
    guidance_model: str | None = None
    k: int = 6


class AiSafetyRisk(BaseModel):
    risk: str
    severity: str
    explanation: str


class AiSafetyCategoryScore(BaseModel):
    score: int
    matched_risk: str | None = None
    explanation: str | None = None


class AiSafetyScoring(BaseModel):
    matched_risks: list[str]
    missed_risks: list[str]
    extra_risks: list[str]
    raw_score: int
    max_score: int
    coverage_score: float
    scores_by_category: dict[str, AiSafetyCategoryScore]


class AiSafetyReport(BaseModel):
    report_title: str
    scenario_summary: dict[str, Any]
    detected_ai_safety_risks: list[AiSafetyRisk]
    risk_severity: list[dict[str, str]]
    matched_risks: list[str]
    missed_risks: list[str]
    coverage_score: float
    recommendations: list[str]
    limitations_and_dual_use_considerations: list[str]


class AiSafetyEvaluationResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    scenario_id: str | None = None
    title: str
    country: str
    healthcare_context: str = ""
    model: str
    identified_risks: list[AiSafetyRisk]
    overall_assessment: str
    scoring: AiSafetyScoring
    report: AiSafetyReport
    raw_model_response: str
    expected_risk_categories: list[str]
    risk_severity: str | None = None
    benchmark_explanation: str | None = None


class AiSafetyFrameworkSource(BaseModel):
    source: str
    excerpt: str


class AiSafetyFrameworkGuidedRecommendation(BaseModel):
    recommendation: str
    rationale: str
    priority: str = "Medium"
    related_risks: list[str] = Field(default_factory=list)
    framework_sources: list[str] = Field(default_factory=list)


class AiSafetyFrameworkGuidedReportResponse(BaseModel):
    scenario_id: str | None = None
    title: str
    country: str = ""
    model: str
    framework_summary: str
    recommendations: list[AiSafetyFrameworkGuidedRecommendation]
    governance_checklist: list[str]
    limitations_and_dual_use_considerations: list[str]
    sources: list[AiSafetyFrameworkSource]
    raw_model_response: str


class AiSafetyBenchmarkAggregate(BaseModel):
    mean_coverage_score_by_model: dict[str, float]
    coverage_score_by_risk_category: dict[str, dict[str, float]]
    coverage_score_by_country: dict[str, dict[str, float]]
    coverage_score_by_severity: dict[str, dict[str, float]]


class AiSafetyBenchmarkResponse(BaseModel):
    models: list[str]
    scenario_count: int
    evaluation_count: int
    aggregate: AiSafetyBenchmarkAggregate
    results: list[AiSafetyEvaluationResponse]


class AiSafetyBenchmarkRunRequest(BaseModel):
    models: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: str

class WorkflowRunRequest(BaseModel):
    filename: str = "mock_device.txt"
    document_text: str = "This is a mock FDA AI medical device submission."
    mock_mode: bool = True


class WorkflowRunResponse(BaseModel):
    workflow_id: str
    status: str
    workflow_type: str
    filename: str
    risk_summary: dict[str, Any] = Field(default_factory=dict)
    escalation_required: bool = False
    escalation_reasons: list[str] = Field(default_factory=list)
    report: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
