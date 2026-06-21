import type {
  AiSafetyBenchmarkResponse,
  AiSafetyEvaluationResponse,
  AiSafetyFrameworkGuidedReportResponse,
  AiSafetyModelsResponse,
  AiSafetyRescoredReviewListResponse,
  AiSafetyScenarioListResponse,
  DeviceListResponse,
  FdaAuditJobCreateResponse,
  FdaAuditJobListResponse,
  FdaAuditJobStatusResponse,
  HealthResponse,
  PrivacyReviewResponse,
  WorkflowRunResponse,
} from "../types/audit";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? String(payload.detail)
        : String(payload);
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  return payload as T;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export function getFdaDevices(): Promise<DeviceListResponse> {
  return request<DeviceListResponse>("/api/fda-audit/devices");
}

export function getAiSafetyScenarios(): Promise<AiSafetyScenarioListResponse> {
  return request<AiSafetyScenarioListResponse>("/api/ai-safety/scenarios");
}

export function getAiSafetyModels(): Promise<AiSafetyModelsResponse> {
  return request<AiSafetyModelsResponse>("/api/ai-safety/models");
}

export function getAiSafetyRescoredReviews(): Promise<AiSafetyRescoredReviewListResponse> {
  return request<AiSafetyRescoredReviewListResponse>("/api/ai-safety/rescored-reviews");
}

export function evaluateAiSafetyScenario(
  scenarioId: string,
  model: string,
): Promise<AiSafetyEvaluationResponse> {
  const params = new URLSearchParams({ model });
  return request<AiSafetyEvaluationResponse>(
    `/api/ai-safety/scenarios/${encodeURIComponent(scenarioId)}/evaluate?${params}`,
    { method: "POST" },
  );
}

export function runAiSafetyBenchmark(models: string[] = []): Promise<AiSafetyBenchmarkResponse> {
  return request<AiSafetyBenchmarkResponse>("/api/ai-safety/benchmark/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ models }),
  });
}

export function evaluateAiSafetyText(payload: {
  title: string;
  country: string;
  text: string;
  expected_risk_categories: string[];
  model: string;
}): Promise<AiSafetyEvaluationResponse> {
  return request<AiSafetyEvaluationResponse>("/api/ai-safety/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function generateAiSafetyFrameworkGuidance(
  scenarioId: string,
  payload: {
    model: string;
    detected_risks: Array<{ risk: string; severity: string; explanation: string }>;
    missed_risks: string[];
    k?: number;
  },
): Promise<AiSafetyFrameworkGuidedReportResponse> {
  return request<AiSafetyFrameworkGuidedReportResponse>(
    `/api/ai-safety/scenarios/${encodeURIComponent(scenarioId)}/framework-guidance`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function generateAiSafetyFrameworkGuidanceFromRescored(
  scenarioId: string,
  payload: {
    source_model: string;
    guidance_model?: string | null;
    k?: number;
  },
): Promise<AiSafetyFrameworkGuidedReportResponse> {
  return request<AiSafetyFrameworkGuidedReportResponse>(
    `/api/ai-safety/scenarios/${encodeURIComponent(scenarioId)}/rescored-framework-guidance`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function uploadAiSafetyDocument(
  file: File,
  options: {
    title?: string;
    country?: string;
    expectedRiskCategories?: string[];
    model: string;
  },
): Promise<AiSafetyEvaluationResponse> {
  const params = new URLSearchParams({
    model: options.model,
    country: options.country ?? "",
  });
  if (options.title) {
    params.set("title", options.title);
  }
  for (const category of options.expectedRiskCategories ?? []) {
    params.append("expected_risk_categories", category);
  }

  const formData = new FormData();
  formData.append("file", file);

  return request<AiSafetyEvaluationResponse>(`/api/ai-safety/upload?${params}`, {
    method: "POST",
    body: formData,
  });
}

export function createFdaDeviceJob(
  filename: string,
  options: { k?: number; saveResult?: boolean } = {},
): Promise<FdaAuditJobCreateResponse> {
  const params = new URLSearchParams({
    k: String(options.k ?? 5),
    save_result: String(options.saveResult ?? true),
  });

  return request<FdaAuditJobCreateResponse>(
    `/api/fda-audit/jobs/devices/${encodeURIComponent(filename)}?${params}`,
    { method: "POST" },
  );
}

export function createFdaUploadJob(
  file: File,
  options: { k?: number; saveResult?: boolean } = {},
): Promise<FdaAuditJobCreateResponse> {
  const params = new URLSearchParams({
    k: String(options.k ?? 5),
    save_result: String(options.saveResult ?? false),
  });
  const formData = new FormData();
  formData.append("file", file);

  return request<FdaAuditJobCreateResponse>(`/api/fda-audit/jobs/upload?${params}`, {
    method: "POST",
    body: formData,
  });
}

export function getFdaJob(jobId: string): Promise<FdaAuditJobStatusResponse> {
  return request<FdaAuditJobStatusResponse>(
    `/api/fda-audit/jobs/${encodeURIComponent(jobId)}`,
  );
}

export function getFdaJobs(): Promise<FdaAuditJobListResponse> {
  return request<FdaAuditJobListResponse>("/api/fda-audit/jobs");
}

export function runFdaWorkflowDevice(filename: string): Promise<WorkflowRunResponse> {
  return request<WorkflowRunResponse>(
    `/api/workflows/fda-audit/devices/${encodeURIComponent(filename)}`,
    { method: "POST" },
  );
}

export function uploadPrivacyReview(file: File): Promise<PrivacyReviewResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return request<PrivacyReviewResponse>("/api/privacy-review/upload", {
    method: "POST",
    body: formData,
  });
}
