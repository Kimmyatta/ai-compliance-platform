from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile

from backend.app.models.schemas import (
    AiSafetyBenchmarkResponse,
    AiSafetyBenchmarkRunRequest,
    AiSafetyEvaluationResponse,
    AiSafetyFrameworkDocumentListResponse,
    AiSafetyFrameworkGuidanceRequest,
    AiSafetyFrameworkGuidedReportResponse,
    AiSafetyFrameworkUploadResponse,
    AiSafetyFrameworksResponse,
    AiSafetyModelsResponse,
    AiSafetyRescoredGuidanceRequest,
    AiSafetyRescoredReviewListResponse,
    AiSafetyScenarioListResponse,
    AiSafetyTextRequest,
    DeviceListResponse,
    FdaAuditJobCreateResponse,
    FdaAuditJobListResponse,
    FdaAuditJobStatusResponse,
    FdaAuditResponse,
    HealthResponse,
    PrivacyReviewResponse,
    WorkflowRunRequest,
    WorkflowRunResponse,
)
from backend.app.services.ai_safety_service import (
    evaluate_ai_safety,
    evaluate_scenario,
    generate_framework_guidance_from_rescored_review,
    generate_framework_guidance_for_scenario,
    list_rescored_reviews,
    list_frameworks,
    list_framework_documents,
    list_models,
    list_scenarios,
    run_full_benchmark,
    save_framework_document,
)
from backend.app.services.fda_audit_service import (
    audit_cleaned_device,
    audit_uploaded_device,
    list_devices,
)
from backend.app.services.pdf_service import extract_text_from_upload
from backend.app.services.privacy_review_service import review_uploaded_document
from backend.app.services.fda_audit_job_service import (
    create_fda_audit_job,
    get_fda_audit_job,
    list_fda_audit_jobs,
    run_cleaned_fda_audit_job,
    run_uploaded_fda_audit_job,
)
from backend.app.services.retrieval_service import (
    afrisafe_frameworks_index_available,
    fda_guidance_index_available,
    privacy_index_available,
)


router = APIRouter(prefix="/api", tags=["AI Compliance Platform"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    return {
        "status": "ok",
        "service": "ai-compliance-platform-api",
        "privacy_index_available": privacy_index_available(),
        "fda_guidance_index_available": fda_guidance_index_available(),
        "afrisafe_frameworks_index_available": afrisafe_frameworks_index_available(),
    }


@router.get("/fda-audit/devices", response_model=DeviceListResponse)
def get_fda_devices():
    return {"devices": list_devices()}


@router.get("/ai-safety/scenarios", response_model=AiSafetyScenarioListResponse)
def get_ai_safety_scenarios():
    return {"scenarios": list_scenarios()}


@router.get("/ai-safety/models", response_model=AiSafetyModelsResponse)
def get_ai_safety_models():
    return {"models": list_models()}


@router.get("/ai-safety/frameworks", response_model=AiSafetyFrameworksResponse)
def get_ai_safety_frameworks():
    return {"frameworks": list_frameworks()}


@router.get(
    "/ai-safety/framework-documents",
    response_model=AiSafetyFrameworkDocumentListResponse,
)
def get_ai_safety_framework_documents():
    return {"documents": list_framework_documents()}


@router.post(
    "/ai-safety/framework-documents/upload",
    response_model=AiSafetyFrameworkUploadResponse,
)
async def upload_ai_safety_framework_document(file: UploadFile = File(...)):
    try:
        return save_framework_document(file.filename or "framework.pdf", await file.read())
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post(
    "/ai-safety/scenarios/{scenario_id}/evaluate",
    response_model=AiSafetyEvaluationResponse,
)
def run_ai_safety_scenario_evaluation(
    scenario_id: str,
    model: str = Query("llama-3.3-70b-versatile"),
):
    try:
        return evaluate_scenario(scenario_id=scenario_id, model=model)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/ai-safety/benchmark/run", response_model=AiSafetyBenchmarkResponse)
def run_ai_safety_full_benchmark(payload: AiSafetyBenchmarkRunRequest):
    try:
        return run_full_benchmark(models=payload.models or None)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post(
    "/ai-safety/scenarios/{scenario_id}/framework-guidance",
    response_model=AiSafetyFrameworkGuidedReportResponse,
)
def run_ai_safety_framework_guidance(
    scenario_id: str,
    payload: AiSafetyFrameworkGuidanceRequest,
):
    try:
        return generate_framework_guidance_for_scenario(
            scenario_id=scenario_id,
            model=payload.model,
            detected_risks=payload.detected_risks,
            missed_risks=payload.missed_risks,
            k=payload.k,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get(
    "/ai-safety/rescored-reviews",
    response_model=AiSafetyRescoredReviewListResponse,
)
def get_ai_safety_rescored_reviews():
    return {"reviews": list_rescored_reviews()}


@router.post(
    "/ai-safety/scenarios/{scenario_id}/rescored-framework-guidance",
    response_model=AiSafetyFrameworkGuidedReportResponse,
)
def run_ai_safety_rescored_framework_guidance(
    scenario_id: str,
    payload: AiSafetyRescoredGuidanceRequest,
):
    try:
        return generate_framework_guidance_from_rescored_review(
            scenario_id=scenario_id,
            source_model=payload.source_model,
            guidance_model=payload.guidance_model,
            k=payload.k,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/ai-safety/evaluate", response_model=AiSafetyEvaluationResponse)
def run_ai_safety_text_evaluation(payload: AiSafetyTextRequest):
    try:
        return evaluate_ai_safety(
            title=payload.title,
            country=payload.country,
            text=payload.text,
            expected_risk_categories=payload.expected_risk_categories,
            model=payload.model,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/ai-safety/upload", response_model=AiSafetyEvaluationResponse)
async def run_ai_safety_upload_evaluation(
    file: UploadFile = File(...),
    title: str | None = Query(None),
    country: str = Query(""),
    expected_risk_categories: list[str] = Query(default=[]),
    model: str = Query("llama-3.3-70b-versatile"),
):
    try:
        filename, document_text = await extract_text_from_upload(file)
        return evaluate_ai_safety(
            title=title or filename,
            country=country,
            text=document_text,
            expected_risk_categories=expected_risk_categories,
            model=model,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/fda-audit/upload", response_model=FdaAuditResponse)
async def run_fda_audit_upload(
    file: UploadFile = File(...),
    k: int = Query(5, ge=1, le=15),
    save_result: bool = Query(False),
):
    try:
        filename, device_text = await extract_text_from_upload(file)
        return audit_uploaded_device(
            filename=filename,
            device_text=device_text,
            k=k,
            save_result=save_result,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/fda-audit/jobs/upload", response_model=FdaAuditJobCreateResponse)
async def create_fda_audit_upload_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    k: int = Query(5, ge=1, le=15),
    save_result: bool = Query(False),
):
    try:
        filename, device_text = await extract_text_from_upload(file)
        job = create_fda_audit_job(filename)
        background_tasks.add_task(
            run_uploaded_fda_audit_job,
            job["job_id"],
            filename,
            device_text,
            k,
            save_result,
        )
        return {
            "job_id": job["job_id"],
            "status": job["status"],
            "filename": job["filename"],
        }
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/fda-audit/jobs", response_model=FdaAuditJobListResponse)
def get_fda_audit_jobs():
    return {"jobs": list_fda_audit_jobs()}


@router.get("/fda-audit/jobs/{job_id}", response_model=FdaAuditJobStatusResponse)
def get_fda_audit_job_status(job_id: str):
    job = get_fda_audit_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="FDA audit job not found.")
    return job


@router.post(
    "/fda-audit/jobs/devices/{filename}",
    response_model=FdaAuditJobCreateResponse,
)
def create_fda_audit_cleaned_device_job(
    filename: str,
    background_tasks: BackgroundTasks,
    k: int = Query(5, ge=1, le=15),
    save_result: bool = Query(True),
):
    try:
        job = create_fda_audit_job(filename)
        background_tasks.add_task(
            run_cleaned_fda_audit_job,
            job["job_id"],
            filename,
            k,
            save_result,
        )
        return {
            "job_id": job["job_id"],
            "status": job["status"],
            "filename": job["filename"],
        }
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/fda-audit/devices/{filename}", response_model=FdaAuditResponse)
def run_fda_audit_cleaned_device(
    filename: str,
    k: int = Query(5, ge=1, le=15),
    save_result: bool = Query(True),
):
    try:
        return audit_cleaned_device(filename=filename, k=k, save_result=save_result)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/privacy-review/upload", response_model=PrivacyReviewResponse)
async def run_privacy_review_upload(file: UploadFile = File(...)):
    try:
        filename, document_text = await extract_text_from_upload(file)
        return review_uploaded_document(filename=filename, document_text=document_text)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/workflows/fda-audit/mock", response_model=WorkflowRunResponse)
def run_mock_fda_audit_workflow(payload: WorkflowRunRequest):
    from backend.app.workflows.compliance_graph import compliance_graph

    workflow_id = str(uuid4())
    result = compliance_graph.invoke(
        {
            "workflow_id": workflow_id,
            "workflow_type": "fda_audit",
            "status": "initialized",
            "mock_mode": payload.mock_mode,
            "filename": payload.filename,
            "document_text": payload.document_text,
        }
    )

    return {
        "workflow_id": workflow_id,
        "status": result.get("status", "unknown"),
        "workflow_type": result.get("workflow_type", "fda_audit"),
        "filename": result.get("filename", payload.filename),
        "risk_summary": result.get("risk_summary", {}),
        "escalation_required": result.get("escalation_required", False),
        "escalation_reasons": result.get("escalation_reasons", []),
        "report": result.get("report", {}),
        "error": result.get("error"),
    }

@router.post("/workflows/fda-audit/devices/{filename}", response_model=WorkflowRunResponse)
def run_real_fda_audit_workflow(filename: str):
    from backend.app.workflows.compliance_graph import compliance_graph
    from document_review_fda import load_device_submission

    workflow_id = str(uuid4())
    document_text = load_device_submission(filename)

    result = compliance_graph.invoke(
        {
            "workflow_id": workflow_id,
            "workflow_type": "fda_audit",
            "status": "initialized",
            "mock_mode": False,
            "filename": filename,
            "document_text": document_text,
        }
    )

    return {
        "workflow_id": workflow_id,
        "status": result.get("status", "unknown"),
        "workflow_type": result.get("workflow_type", "fda_audit"),
        "filename": result.get("filename", filename),
        "risk_summary": result.get("risk_summary", {}),
        "escalation_required": result.get("escalation_required", False),
        "escalation_reasons": result.get("escalation_reasons", []),
        "report": result.get("report", {}),
        "error": result.get("error"),
    }
