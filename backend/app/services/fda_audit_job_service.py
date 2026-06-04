from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from backend.app.services.fda_audit_service import (
    audit_cleaned_device,
    audit_uploaded_device,
)


_jobs = {}
_jobs_lock = Lock()


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _public_job(job):
    return deepcopy(job)


def _update_job(job_id, **updates):
    with _jobs_lock:
        if job_id not in _jobs:
            raise KeyError(f"FDA audit job not found: {job_id}")
        _jobs[job_id].update(updates)
        _jobs[job_id]["updated_at"] = _now_iso()
        return _public_job(_jobs[job_id])


def create_fda_audit_job(filename):
    job_id = str(uuid4())
    timestamp = _now_iso()
    job = {
        "job_id": job_id,
        "status": "queued",
        "filename": filename,
        "created_at": timestamp,
        "updated_at": timestamp,
        "result": None,
        "error": None,
    }
    with _jobs_lock:
        _jobs[job_id] = job
    return _public_job(job)


def get_fda_audit_job(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        return _public_job(job)


def list_fda_audit_jobs():
    with _jobs_lock:
        return [
            _public_job(job)
            for job in sorted(
                _jobs.values(),
                key=lambda item: item["created_at"],
                reverse=True,
            )
        ]


def run_uploaded_fda_audit_job(job_id, filename, device_text, k=5, save_result=False):
    try:
        _update_job(job_id, status="running", error=None)
        result = audit_uploaded_device(
            filename=filename,
            device_text=device_text,
            k=k,
            save_result=save_result,
        )
        _update_job(job_id, status="completed", result=result, error=None)
    except Exception as error:
        _update_job(job_id, status="failed", error=str(error), result=None)


def run_cleaned_fda_audit_job(job_id, filename, k=5, save_result=True):
    try:
        _update_job(job_id, status="running", error=None)
        result = audit_cleaned_device(
            filename=filename,
            k=k,
            save_result=save_result,
        )
        _update_job(job_id, status="completed", result=result, error=None)
    except Exception as error:
        _update_job(job_id, status="failed", error=str(error), result=None)
