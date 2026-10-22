export const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8011').replace(/\/$/, '');

let providerRetryAt = 0;
export const aiRetryUntil = () => providerRetryAt;

export class ApiError extends Error {
  constructor(message: string, public status: number, public retryAfter: number | null = null, public detail: unknown = null) {
    super(message); this.name = 'ApiError';
  }
}

export async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API}/api${path}`, body === undefined ? {} : {
    method: 'POST',
    headers: body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    body: body instanceof FormData ? body : JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    let retryAfter: number | null = null;
    if (response.status === 429) {
      const value = response.headers.get('Retry-After');
      const delay = value && /^\d+(\.\d+)?$/.test(value) ? Number(value) : value ? (Date.parse(value) - Date.now()) / 1000 : NaN;
      retryAfter = Number.isFinite(delay) ? Math.min(3600, Math.max(1, Math.ceil(delay))) : 60;
      providerRetryAt = Math.max(providerRetryAt, Date.now() + retryAfter * 1000);
    }
    const detail = payload?.detail;
    throw new ApiError(typeof detail === 'string' ? detail : typeof detail?.message === 'string' ? detail.message : `Request failed (${response.status}).`, response.status, retryAfter, detail);
  }
  return response.json();
}

export interface Matter {
  id: string; name: string; reference: string; description: string;
  created_at: string; document_count: number;
}
export interface LegalDocument {
  id: string; title: string; filename: string; kind: 'judgment' | 'statute' | 'matter';
  matter_id: string | null; court: string; citation: string; decision_date: string;
  source_url: string; created_at: string; unit_count: number; chunk_count: number;
}
export interface Source {
  chunk_id: number; document_id: string; title: string; filename: string;
  locator: string; text: string; kind: string; court: string; citation: string;
  decision_date: string; source_url: string;
}
export interface LegalReport {
  id: string; kind: string; matter_id: string | null; query: string; created_at: string;
  payload: {
    title: string; findings: { text: string; source_ids: number[]; category?: 'comparison' | 'possible_approach' | 'evidence_gap'; supporting_quotes?: { source_id: number; quote: string }[] }[];
    grounding_version?: number;
    workflow?: string;
    claim_format?: string;
    case_evidence?: CaseEvidence;
    scope?: string;
    brief?: Brief;
    issue_reports?: WorkflowIssue[];
    warning?: string;
    claims?: EvidenceClaim[];
    verification?: VerificationSummary;
    evidence_texts?: Record<EvidenceRole, string>;
    comparison?: { status: 'limited_comparison' | 'insufficient_authority' };
    reviewed_evidence?: { contract: ReviewedQuote; authority: ReviewedQuote };
    evidence_selection?: { mode: 'ai_selected' | 'manual_after_role_flag'; warning: string; model: string; human_confirmed: string[]; original_issues?: RoleIssue[] };
    limitations: string[]; sources: Source[]; confirmed_facts?: string; confirmed_issues?: string[];
  };
}
export type EvidenceRole = 'contract' | 'authority' | 'facts';
export interface EvidenceSpan {
  role: EvidenceRole; text: string; source_id: number | null; start: number | null; end: number | null;
}
export interface CaseUnit {
  id: string; source_id: number; text: string; start: number; end: number;
}
export interface CaseEvidence {
  version: string; text: string; units: CaseUnit[]; sources: Source[];
  topics: Record<'notice_and_cure' | 'remedial_access' | 'material_breach', string[]>;
  coverage: { passages_considered: number; units_considered: number; units_selected: number; incomplete: boolean };
  warning: string;
}
export interface VerificationSummary {
  version: string; state: 'complete' | 'partial' | 'unavailable' | 'skipped'; model: string; created_at: string;
  total_claims: number; eligible_claims: number; model_assessed: number; gate_assessed: number; blocked_claims: number;
  retry_after: number | null; notes: string[]; warning: string;
  policy_version?: string; withheld_model_support?: number;
}
export interface EvidenceClaim {
  id: string; scope: 'contract_term' | 'case_fact' | 'general_principle' | 'authority_case_only' | 'comparison' | 'not_established';
  text: string; evidence_check: 'matched' | 'flagged' | 'no_evidence';
  application_topic?: 'notice_and_cure' | 'remedial_access' | 'material_breach';
  wording_origin?: 'source_text' | 'model_application' | 'review_question';
  factual_origin?: 'case_document';
  issue_key?: string;
  report_kind?: string;
  display_state?: 'source_excerpt' | 'draft_for_review' | 'evidence_gap' | 'withheld';
  application_alignment?: 'aligned_sources' | 'evidence_gap';
  check_issues: string[]; semantic_status: 'not_checked' | 'supported' | 'contradicted' | 'insufficient_evidence';
  spans: EvidenceSpan[];
  verification?: { origin: 'model' | 'evidence_gate' | 'policy_gate' | 'not_checked'; reason: string; evidence: EvidenceSpan[]; model_verdict?: string; model_reason?: string };
}
export interface ReviewedQuote { source_id: number; quote: string }
export interface TerminationEvidence { case_passages: Source[]; authority_passages: Source[]; coverage: string }
export interface AutomaticEvidence {
  selection_id: string; created_at: string; expires_at: string; warning: string;
  contract: { source: Source; quote: string; role: string };
  authority: { source: Source; quote: string; role: string };
  coverage: { note: string; contract: { candidates: number; assessed: number; reduced: boolean }; authority: { candidates: number; assessed: number; reduced: boolean } };
}
export interface RoleIssue { role: 'contract' | 'authority'; code: string; message: string }
export interface EvidenceRoleReview {
  review_id: string; issues: RoleIssue[];
  contract: AutomaticEvidence['contract']; authority: AutomaticEvidence['authority'];
}
export function blockedEvidenceReview(error: unknown): EvidenceRoleReview | null {
  if (!(error instanceof ApiError) || error.status !== 422 || !error.detail || typeof error.detail !== 'object') return null;
  const detail = error.detail as { code?: string; review?: EvidenceRoleReview };
  return detail.code === 'evidence_role_review_required' && detail.review?.review_id && Array.isArray(detail.review.issues)
    && detail.review.contract?.source && detail.review.authority?.source ? detail.review : null;
}
export interface Dashboard {
  matters: number; matter_documents: number; judgments: number; statutes: number;
  reports: number; library_updated_at: string | null;
  recent_documents: LegalDocument[]; recent_reports: LegalReport[];
}
export interface Health { ai_configured: boolean; model: string }
export interface Brief { facts: string; issues: string[]; missing_information: string[]; sources: Source[]; truncated: boolean; fact_excerpts?: CaseUnit[]; warning?: string }
export interface WorkflowIssue {
  key: string; title: string; claims: EvidenceClaim[]; sources: Source[]; notes: string[];
  coverage?: { candidates?: number; assessed?: number; issue_units_selected?: number; issue_units_available?: number };
  selected_evidence?: { contract: ReviewedQuote; authority: ReviewedQuote };
}
export interface AnalysisJob {
  id: string; matter_id: string; status: 'queued' | 'running' | 'paused' | 'completed' | 'stale';
  stage: string; progress: number; message: string; retry_at: string | null;
  report_id: string | null; report: LegalReport | null; created_at: string; updated_at: string;
}

export const documentUrl = (id: string) => `${API}/api/documents/${id}/download`;

export function downloadReport(report: LegalReport) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `legal-report-${report.id}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
