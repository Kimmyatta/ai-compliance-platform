export type JobStatus = "queued" | "running" | "completed" | "failed";

export type HealthResponse = {
  status: string;
  service: string;
  privacy_index_available: boolean;
  fda_guidance_index_available: boolean;
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
