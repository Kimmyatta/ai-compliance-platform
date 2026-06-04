from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from backend.app.models.schemas import (
    DeviceListResponse,
    FdaAuditResponse,
    HealthResponse,
    PrivacyReviewResponse,
)
from backend.app.services.fda_audit_service import (
    audit_cleaned_device,
    audit_uploaded_device,
    list_devices,
)
from backend.app.services.pdf_service import extract_text_from_upload
from backend.app.services.privacy_review_service import review_uploaded_document
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
