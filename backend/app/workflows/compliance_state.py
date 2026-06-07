from typing import Any, Literal, TypedDict


WorkflowStatus = Literal[
    "initialized",
    "intake_complete",
    "retrieval_complete",
    "review_complete",
    "risk_scored",
    "report_generated",
    "escalation_required",
    "completed",
    "failed",
]


class ComplianceWorkflowState(TypedDict, total=False):
    workflow_id: str
    workflow_type: Literal["fda_audit", "privacy_review"]
    status: WorkflowStatus
    mock_mode: bool

    filename: str
    document_text: str

    retrieval_results: dict[str, Any]
    guidance_context: str
    guidance_sources: list[str]
    device_evidence: str
    device_evidence_sources: list[dict[str, Any]]

    audit_result: dict[str, Any]
    risk_summary: dict[str, Any]
    report: dict[str, Any]

    escalation_required: bool
    escalation_reasons: list[str]

    error: str
