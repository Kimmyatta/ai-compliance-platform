from groq import Groq

from backend.app.core.config import require_groq_api_key


def _get_client():
    return Groq(api_key=require_groq_api_key())


def _build_dimension_response(dimension, result, parse_audit_result):
    audit_text = result.get("audit", "")
    parsed = parse_audit_result(audit_text) if audit_text else {}

    return {
        "dimension": dimension,
        "status": result.get("status", "completed"),
        "guidance": result.get("guidance", ""),
        "risk_level": parsed.get("risk_level", "UNKNOWN"),
        "parsed": parsed,
        "audit": audit_text,
        "error": result.get("error", ""),
        "sources": result.get("sources", []),
        "device_evidence": result.get("device_evidence", []),
        "principles": result.get("principles", []),
    }


def _build_response(filename, raw_result, saved_result_path=None):
    from document_review_fda import parse_audit_result

    audits = raw_result.get("audits", {})
    return {
        "filename": filename,
        "summary": raw_result.get("summary", {}),
        "audits": [
            _build_dimension_response(dimension, result, parse_audit_result)
            for dimension, result in audits.items()
        ],
        "saved_result_path": str(saved_result_path) if saved_result_path else None,
    }


def list_devices():
    from document_review_fda import list_device_submissions

    return list_device_submissions()


def audit_uploaded_device(filename, device_text, k=5, save_result=False):
    from document_review_fda import audit_device_submission, save_audit_result

    raw_result = audit_device_submission(device_text, _get_client(), k=k)
    saved_result_path = save_audit_result(filename, raw_result) if save_result else None
    return _build_response(filename, raw_result, saved_result_path=saved_result_path)


def audit_cleaned_device(filename, k=5, save_result=True):
    from document_review_fda import audit_device_file, save_audit_result

    raw_result = audit_device_file(filename, _get_client(), k=k)
    saved_result_path = save_audit_result(filename, raw_result) if save_result else None
    return _build_response(filename, raw_result, saved_result_path=saved_result_path)
