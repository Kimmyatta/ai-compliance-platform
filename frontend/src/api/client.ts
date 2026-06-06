import type {
  DeviceListResponse,
  FdaAuditJobCreateResponse,
  FdaAuditJobListResponse,
  FdaAuditJobStatusResponse,
  HealthResponse,
  PrivacyReviewResponse,
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

export function uploadPrivacyReview(file: File): Promise<PrivacyReviewResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return request<PrivacyReviewResponse>("/api/privacy-review/upload", {
    method: "POST",
    body: formData,
  });
}
