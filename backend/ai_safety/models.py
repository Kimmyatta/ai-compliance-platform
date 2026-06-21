from typing import Any

from pydantic import BaseModel, Field


RISK_CATEGORIES = [
    "Bias and Fairness",
    "Human Oversight",
    "Transparency and Explainability",
    "Safety and Reliability",
    "Data Governance and Privacy",
    "Monitoring and Incident Reporting",
    "Distribution Shift and Local Validation",
    "Vendor Dependency",
    "Resource-Constrained Deployment",
    "Misinformation or Unsafe Medical Advice",
]

DEFAULT_MODEL = "llama-3.3-70b-versatile"
BENCHMARK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-20b",
]


class Scenario(BaseModel):
    scenario_id: str
    title: str
    country: str
    healthcare_context: str = ""
    scenario_description: str
    expected_risk_categories: list[str]
    risk_severity: str = "Unknown"
    explanation: str


class IdentifiedRisk(BaseModel):
    risk: str
    explanation: str
    severity: str


class ModelEvaluationOutput(BaseModel):
    identified_risks: list[IdentifiedRisk] = Field(default_factory=list)
    overall_assessment: str = ""


class CategoryScore(BaseModel):
    score: int
    matched_risk: str | None = None
    explanation: str | None = None


class ScenarioScore(BaseModel):
    matched_risks: list[str]
    missed_risks: list[str]
    extra_risks: list[str]
    raw_score: int
    max_score: int
    coverage_score: float
    scores_by_category: dict[str, CategoryScore]


class SafetyReport(BaseModel):
    report_title: str
    scenario_summary: dict[str, Any]
    detected_ai_safety_risks: list[IdentifiedRisk]
    risk_severity: list[dict[str, str]]
    matched_risks: list[str]
    missed_risks: list[str]
    coverage_score: float
    recommendations: list[str]
    limitations_and_dual_use_considerations: list[str]


class FrameworkSource(BaseModel):
    source: str
    excerpt: str


class FrameworkGuidedRecommendation(BaseModel):
    recommendation: str
    rationale: str
    priority: str = "Medium"
    related_risks: list[str] = Field(default_factory=list)
    framework_sources: list[str] = Field(default_factory=list)


class FrameworkGuidedReport(BaseModel):
    scenario_id: str | None = None
    title: str
    country: str = ""
    model: str
    framework_summary: str
    recommendations: list[FrameworkGuidedRecommendation]
    governance_checklist: list[str]
    limitations_and_dual_use_considerations: list[str]
    sources: list[FrameworkSource]
    raw_model_response: str


class EvaluationResult(BaseModel):
    scenario_id: str | None = None
    title: str
    country: str
    healthcare_context: str = ""
    model: str
    identified_risks: list[IdentifiedRisk]
    overall_assessment: str
    scoring: ScenarioScore
    report: SafetyReport
    raw_model_response: str
    expected_risk_categories: list[str]
    risk_severity: str | None = None
    benchmark_explanation: str | None = None


class BenchmarkAggregate(BaseModel):
    mean_coverage_score_by_model: dict[str, float]
    coverage_score_by_risk_category: dict[str, dict[str, float]]
    coverage_score_by_country: dict[str, dict[str, float]]
    coverage_score_by_severity: dict[str, dict[str, float]]


class BenchmarkRunResult(BaseModel):
    models: list[str]
    scenario_count: int
    evaluation_count: int
    aggregate: BenchmarkAggregate
    results: list[EvaluationResult]
