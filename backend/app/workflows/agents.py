from typing import Any

from groq import Groq

from backend.app.core.config import require_groq_api_key
from backend.app.workflows.compliance_state import ComplianceWorkflowState
from document_review_fda import (
    FDA_AUDIT_DIMENSIONS,
    audit_device_submission,
    build_device_evidence_index,
    get_device_evidence_context,
    get_guidance_context,
    parse_audit_result,
)


def intake_agent(state: ComplianceWorkflowState) -> ComplianceWorkflowState:
    if not state.get("filename"):
        return {
            **state,
            "status": "failed",
            "error": "Missing filename for workflow intake.",
        }

    if not state.get("document_text"):
        return {
            **state,
            "status": "failed",
            "error": "Missing document text for workflow intake.",
        }

    return {
        **state,
        "status": "intake_complete",
    }


def retrieval_agent(state: ComplianceWorkflowState) -> ComplianceWorkflowState:
    document_text = state.get("document_text", "")
    if not document_text:
        return {
            **state,
            "status": "failed",
            "error": "Cannot retrieve evidence without document text.",
        }

    if state.get("mock_mode"):
        return {
            **state,
            "status": "retrieval_complete",
            "retrieval_results": {
                "Mock FDA Audit Dimension": {
                    "guidance": "Mock FDA Guidance",
                    "principles": ["Mock principle"],
                    "guidance_context": "Mock guidance context.",
                    "guidance_sources": ["mock_guidance_source.txt"],
                    "device_evidence": "Mock device evidence.",
                    "device_evidence_sources": [
                        {
                            "chunk": 1,
                            "start": 0,
                            "end": len(document_text),
                        }
                    ],
                }
            },
        }

    device_chunks, device_index = build_device_evidence_index(document_text)

    retrieval_results: dict[str, Any] = {}

    for dimension, config in FDA_AUDIT_DIMENSIONS.items():
        guidance_context, guidance_sources = get_guidance_context(
            config["query"],
            source_prefixes=config["source_prefixes"],
        )
        device_evidence, device_evidence_sources = get_device_evidence_context(
            query=config["query"],
            principles=config["principles"],
            chunks=device_chunks,
            index=device_index,
        )

        retrieval_results[dimension] = {
            "guidance": config["guidance"],
            "principles": config["principles"],
            "guidance_context": guidance_context,
            "guidance_sources": guidance_sources,
            "device_evidence": device_evidence,
            "device_evidence_sources": device_evidence_sources,
        }

    return {
        **state,
        "status": "retrieval_complete",
        "retrieval_results": retrieval_results,
    }


def compliance_review_agent(state: ComplianceWorkflowState) -> ComplianceWorkflowState:
    document_text = state.get("document_text", "")
    if not document_text:
        return {
            **state,
            "status": "failed",
            "error": "Cannot run compliance review without document text.",
        }

    if state.get("mock_mode"):
        audit_result = {
            "audits": {
                "Mock FDA Audit Dimension": {
                    "status": "completed",
                    "audit": """Audit Summary:
Mock audit completed without calling Groq.

Principle-by-Principle Assessment:
- Principle: Mock principle
  Feature Scope: Mock AI feature
  Status: NOT DISCLOSED
  Submission Evidence: Mock evidence
  Analysis: Mock analysis

Guidance-Alignment Gaps:
Mock guidance gap.

Insufficient Public Disclosure:
Mock insufficient disclosure.

Potential Regulatory Concerns:
Mock regulatory concern.

Potential Violations:
None identified from the provided public submission.

Risk Level:
HIGH

Recommendations:
Mock recommendation.""",
                    "error": "",
                    "sources": [],
                    "guidance": "Mock FDA Guidance",
                    "principles": ["Mock principle"],
                    "device_evidence": [],
                }
            },
            "summary": {
                "total_dimensions": 1,
                "completed_dimensions": 1,
                "failed_dimensions": 0,
                "skipped_dimensions": 0,
                "has_errors": False,
                "all_failed": False,
            },
        }

        return {
            **state,
            "status": "review_complete",
            "audit_result": audit_result,
        }

    client = Groq(api_key=require_groq_api_key())

    audit_result = audit_device_submission(
        document_text,
        client,
    )

    return {
        **state,
        "status": "review_complete",
        "audit_result": audit_result,
    }


def risk_scoring_agent(state: ComplianceWorkflowState) -> ComplianceWorkflowState:
    audit_result = state.get("audit_result", {})
    audits = audit_result.get("audits", {})

    risk_counts = {
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0,
        "UNKNOWN": 0,
        "NOT APPLICABLE": 0,
    }
    not_disclosed_count = 0
    escalation_reasons: list[str] = []

    for dimension, result in audits.items():
        audit_text = result.get("audit", "")
        parsed = parse_audit_result(audit_text) if audit_text else {}
        risk = parsed.get("risk_level", "UNKNOWN").upper()

        if risk not in risk_counts:
            risk = "UNKNOWN"

        risk_counts[risk] += 1

        principle_text = parsed.get("principle_assessment", "").upper()
        not_disclosed_count += principle_text.count("NOT DISCLOSED")

        if risk == "HIGH":
            escalation_reasons.append(f"HIGH risk finding in {dimension}")
        if risk == "UNKNOWN":
            escalation_reasons.append(f"UNKNOWN risk finding in {dimension}")

    if not_disclosed_count >= 3:
        escalation_reasons.append(
            f"{not_disclosed_count} NOT DISCLOSED findings require human review"
        )

    if risk_counts["HIGH"] > 0:
        overall_risk = "HIGH"
    elif risk_counts["MEDIUM"] > 0:
        overall_risk = "MEDIUM"
    elif risk_counts["UNKNOWN"] > 0:
        overall_risk = "UNKNOWN"
    else:
        overall_risk = "LOW"

    return {
        **state,
        "status": "risk_scored",
        "risk_summary": {
            "overall_risk": overall_risk,
            "risk_counts": risk_counts,
            "not_disclosed_count": not_disclosed_count,
        },
        "escalation_required": bool(escalation_reasons),
        "escalation_reasons": escalation_reasons,
    }


def report_generation_agent(state: ComplianceWorkflowState) -> ComplianceWorkflowState:
    report = {
        "workflow_id": state.get("workflow_id"),
        "workflow_type": state.get("workflow_type"),
        "filename": state.get("filename"),
        "audit_result": state.get("audit_result", {}),
        "risk_summary": state.get("risk_summary", {}),
        "escalation_required": state.get("escalation_required", False),
        "escalation_reasons": state.get("escalation_reasons", []),
    }

    return {
        **state,
        "status": "report_generated",
        "report": report,
    }


def escalation_agent(state: ComplianceWorkflowState) -> ComplianceWorkflowState:
    if state.get("escalation_required"):
        return {
            **state,
            "status": "escalation_required",
        }

    return {
        **state,
        "status": "completed",
    }

