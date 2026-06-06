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
