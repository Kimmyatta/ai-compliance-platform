export type JobStatus = "queued" | "running" | "completed" | "failed";

export type HealthResponse = {
  status: string;
  service: string;
  privacy_index_available: boolean;
  fda_guidance_index_available: boolean;
  afrisafe_frameworks_index_available: boolean;
};

export type DeviceListResponse = {
  devices: string[];
};

export type FdaAuditSummary = {
  total_dimensions: number;
  completed_dimensions: number;
  failed_dimensions: number;
  skipped_dimensions: number;
  has_errors: boolean;
  all_failed: boolean;
};

export type FdaAuditDimension = {
  dimension: string;
  status: string;
  guidance: string;
  risk_level: string;
  parsed: Record<string, string>;
  audit: string;
  error: string;
  sources: string[];
  device_evidence: Array<Record<string, unknown>>;
  principles: string[];
};

export type FdaAuditResponse = {
  filename: string;
  summary: FdaAuditSummary;
  audits: FdaAuditDimension[];
  saved_result_path: string | null;
};

export type FdaAuditJobCreateResponse = {
  job_id: string;
  status: JobStatus;
  filename: string;
};

export type FdaAuditJobStatusResponse = {
  job_id: string;
  status: JobStatus;
  filename: string;
  created_at: string;
  updated_at: string;
  current_dimension: string | null;
  current_dimension_index: number;
  total_dimensions: number;
  completed_dimensions: number;
  progress_percent: number;
  message: string | null;
  result: FdaAuditResponse | null;
  error: string | null;
};

export type FdaAuditJobListResponse = {
  jobs: FdaAuditJobStatusResponse[];
};

export type PrivacyReviewResult = {
  regulation: string;
  parsed: Record<string, string>;
  review: string;
};

export type PrivacyReviewResponse = {
  filename: string;
  reviews: PrivacyReviewResult[];
};

export type AiSafetyModel = {
  id: string;
  label: string;
};

export type AiSafetyScenario = {
  scenario_id: string;
  title: string;
  country: string;
  healthcare_context: string;
  scenario_description: string;
  expected_risk_categories: string[];
  risk_severity: string;
  severity: string;
  explanation: string;
};

export type AiSafetyScenarioListResponse = {
  scenarios: AiSafetyScenario[];
};

export type AiSafetyModelsResponse = {
  models: AiSafetyModel[];
};

export type AiSafetyRescoredReview = {
  review_id: string;
  scenario_id: string;
  title: string;
  country: string;
  model: string;
  coverage_score: number;
  missed_risks: string[];
  path: string;
};

export type AiSafetyRescoredReviewListResponse = {
  reviews: AiSafetyRescoredReview[];
};

export type AiSafetyRisk = {
  risk: string;
  severity: string;
  explanation: string;
};

export type AiSafetyCategoryScore = {
  score: number;
  matched_risk: string | null;
  explanation: string | null;
};

export type AiSafetyScoring = {
  matched_risks: string[];
  missed_risks: string[];
  extra_risks: string[];
  raw_score: number;
  max_score: number;
  coverage_score: number;
  scores_by_category: Record<string, AiSafetyCategoryScore>;
};

export type AiSafetyReport = {
  report_title: string;
  scenario_summary: Record<string, unknown>;
  detected_ai_safety_risks: AiSafetyRisk[];
  risk_severity: Array<Record<string, string>>;
  matched_risks: string[];
  missed_risks: string[];
  coverage_score: number;
  recommendations: string[];
  limitations_and_dual_use_considerations: string[];
};

export type AiSafetyEvaluationResponse = {
  scenario_id: string | null;
  title: string;
  country: string;
  healthcare_context: string;
  model: string;
  identified_risks: AiSafetyRisk[];
  overall_assessment: string;
  scoring: AiSafetyScoring;
  report: AiSafetyReport;
  raw_model_response: string;
  expected_risk_categories: string[];
  risk_severity: string | null;
  benchmark_explanation: string | null;
};

export type AiSafetyFrameworkSource = {
  source: string;
  excerpt: string;
};

export type AiSafetyFrameworkGuidedRecommendation = {
  recommendation: string;
  rationale: string;
  priority: string;
  related_risks: string[];
  framework_sources: string[];
};

export type AiSafetyFrameworkGuidedReportResponse = {
  scenario_id: string | null;
  title: string;
  country: string;
  model: string;
  framework_summary: string;
  recommendations: AiSafetyFrameworkGuidedRecommendation[];
  governance_checklist: string[];
  limitations_and_dual_use_considerations: string[];
  sources: AiSafetyFrameworkSource[];
  raw_model_response: string;
};

export type AiSafetyBenchmarkAggregate = {
  mean_coverage_score_by_model: Record<string, number>;
  coverage_score_by_risk_category: Record<string, Record<string, number>>;
  coverage_score_by_country: Record<string, Record<string, number>>;
  coverage_score_by_severity: Record<string, Record<string, number>>;
};

export type AiSafetyBenchmarkResponse = {
  models: string[];
  scenario_count: number;
  evaluation_count: number;
  aggregate: AiSafetyBenchmarkAggregate;
  results: AiSafetyEvaluationResponse[];
};

export type WorkflowRiskSummary = {
  overall_risk: string;
  risk_counts: Record<string, number>;
  not_disclosed_count: number;
};

export type WorkflowAuditDimension = {
  status: string;
  audit: string;
  error: string;
  sources: string[];
  guidance: string;
  principles: string[];
  device_evidence: Array<Record<string, unknown>>;
  determination?: string;
};

export type WorkflowAuditResult = {
  audits: Record<string, WorkflowAuditDimension>;
  summary: FdaAuditSummary;
};

export type WorkflowReport = {
  workflow_id: string;
  workflow_type: string;
  filename: string;
  audit_result: WorkflowAuditResult;
  risk_summary: WorkflowRiskSummary;
  escalation_required: boolean;
  escalation_reasons: string[];
};

export type WorkflowRunResponse = {
  workflow_id: string;
  status: string;
  workflow_type: string;
  filename: string;
  risk_summary: WorkflowRiskSummary;
  escalation_required: boolean;
  escalation_reasons: string[];
  report: WorkflowReport;
  error: string | null;
};
