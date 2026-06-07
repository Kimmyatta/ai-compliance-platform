from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile

from backend.app.models.schemas import (
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
    }


@router.get("/fda-audit/devices", response_model=DeviceListResponse)
def get_fda_devices():
    return {"devices": list_devices()}


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