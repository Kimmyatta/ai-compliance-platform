import hashlib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from zipfile import BadZipFile

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import load_settings
from .documents import MAX_UPLOAD_BYTES, extract_units, split_units
from .intelligence import Intelligence
from .evidence_selection import compare_after_manual_review, compare_automatic, prepare_evidence
from .schemas import AutomaticEvidenceRequest, AutomaticTerminationRequest, CaseAnalysisRequest, CaseRequest, MatterCreate, ResearchRequest, SearchRequest, TerminationRequest
from .store import Store
from .termination import ISSUE, compare_termination, evidence_candidates, reverify_report
from .case_workflow import create_job, fingerprint, public_job, run_job


def create_app(data_dir: Path | None = None) -> FastAPI:
    settings = load_settings(data_dir)
    store = Store(settings.data_dir)
    @asynccontextmanager
    async def lifespan(_app):
        store.recover_analysis_jobs()
        yield

    app = FastAPI(title="Ghana Legal Workspace API", version="0.1.0", lifespan=lifespan)
    app.state.store = store
    app.state.intelligence = Intelligence(settings)
    app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins],
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"], expose_headers=['Retry-After'])

    def require_matter(matter_id):
        if not matter_id or not store.matter(matter_id):
            raise HTTPException(404, "Select an existing matter.")

    def validate_scope(payload):
        if payload.scope in {"matter", "both"}:
            require_matter(payload.matter_id)

    @app.get("/api/health")
    def health():
        return {"service": "Ghana Legal Workspace", "ai_configured": bool(settings.api_key),
                "model": settings.model, "search": "SQLite FTS5 keyword ranking",
                "parent_project": "AI Compliance Platform", "mode": "local-single-workspace"}

    @app.get("/api/dashboard")
    def dashboard():
        return store.dashboard()

    @app.get("/api/matters")
    def matters():
        return store.matters()

    @app.post("/api/matters", status_code=201)
    def create_matter(payload: MatterCreate):
        values = {key: value.strip() for key, value in payload.model_dump().items()}
        if not values["name"]:
            raise HTTPException(422, "Enter a matter name.")
        return store.create_matter(values)

    @app.get("/api/documents")
    def documents():
        return store.documents()

    @app.post("/api/documents")
    def upload_document(
        file: Annotated[UploadFile, File()],
        kind: Annotated[Literal["judgment", "statute", "matter"], Form()],
        title: Annotated[str, Form(max_length=240)] = "",
        matter_id: Annotated[str, Form()] = "",
        court: Annotated[str, Form(max_length=160)] = "",
        citation: Annotated[str, Form(max_length=240)] = "",
        decision_date: Annotated[str, Form(max_length=40)] = "",
        source_url: Annotated[str, Form(max_length=2000)] = "",
        permission_note: Annotated[str, Form(max_length=1000)] = "",
        permission_confirmed: Annotated[bool, Form()] = False,
    ):
        if kind == "matter":
            require_matter(matter_id)
        elif matter_id:
            raise HTTPException(422, "Library authorities cannot be assigned to a private matter.")
        if not permission_confirmed:
            raise HTTPException(422, "Confirm you are authorised to store and process this document.")
        if source_url and not source_url.startswith(("https://", "http://")):
            raise HTTPException(422, "Source URL must start with https:// or http://.")
        filename = (file.filename or "document").replace("\\", "/").rsplit("/", 1)[-1][:240]
        try:
            content = file.file.read(MAX_UPLOAD_BYTES + 1)
        finally:
            file.file.close()
        if not content:
            raise HTTPException(422, "Uploaded file is empty.")
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Upload a document smaller than 20 MB.")
        try:
            units = extract_units(filename, content)
            chunks = split_units(units)
        except (ValueError, BadZipFile) as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(422, "This document could not be read. Check the file and try again.") from exc
        return store.add_document({
            "filename": filename, "title": title.strip() or filename,
            "kind": kind, "matter_id": matter_id if kind == "matter" else None,
            "court": court.strip(), "citation": citation.strip(),
            "decision_date": decision_date, "source_url": source_url,
            "permission_note": permission_note.strip(),
            "sha256": hashlib.sha256(content).hexdigest(),
        }, content, units, chunks)

    @app.get("/api/documents/{document_id}/download")
    def download(document_id: str):
        document = store.document(document_id)
        if not document:
            raise HTTPException(404, "Document not found.")
        return FileResponse(store.upload_dir / document["id"], filename=document["filename"],
                            media_type="application/octet-stream")

    @app.get("/api/passages/{chunk_id}")
    def passage(chunk_id: int):
        source = store.source(chunk_id)
        if not source:
            raise HTTPException(404, "Source passage not found.")
        return source

    @app.post("/api/search")
    def search(payload: SearchRequest):
        validate_scope(payload)
        return store.search(payload.query, payload.matter_id, payload.scope)

    @app.post("/api/research")
    def research(payload: ResearchRequest):
        validate_scope(payload)
        sources = store.search(payload.query, payload.matter_id, payload.scope)
        if not sources:
            raise HTTPException(422, "No matching passages found. Upload relevant authorities or change the search terms.")
        report = app.state.intelligence.report(payload.query, sources)
        return store.save_report("research", payload.matter_id, payload.query, report)

    @app.post("/api/case-analysis/brief")
    def brief(payload: CaseRequest):
        require_matter(payload.matter_id)
        sources, truncated = store.matter_passages(payload.matter_id)
        if not sources:
            raise HTTPException(422, "Upload case documents to this matter first.")
        return app.state.intelligence.brief(sources, truncated)

    @app.post('/api/case-analysis/jobs', status_code=202)
    def start_case_job(payload: CaseRequest, tasks: BackgroundTasks):
        require_matter(payload.matter_id)
        job = create_job(app.state.intelligence, store, payload.matter_id)
        if job['status'] == 'paused' and (not job.get('retry_at') or datetime.fromisoformat(job['retry_at']) <= datetime.now(timezone.utc)):
            job.update(status='queued', message='Resuming saved analysis steps.')
            store.save_analysis_job(job)
        tasks.add_task(run_job, app.state.intelligence, store, job['id'])
        return public_job(store, job)

    @app.get('/api/case-analysis/jobs')
    def case_jobs(matter_id: str):
        require_matter(matter_id)
        return [public_job(store, job) for job in store.analysis_jobs(matter_id)]

    @app.get('/api/case-analysis/jobs/{job_id}')
    def get_case_job(job_id: str):
        job = store.analysis_job(job_id)
        if not job:
            raise HTTPException(404, 'Analysis job not found.')
        require_matter(job['matter_id'])
        return public_job(store, job)

    @app.post('/api/case-analysis/jobs/{job_id}/resume', status_code=202)
    def resume_case_job(job_id: str, tasks: BackgroundTasks):
        job = store.analysis_job(job_id)
        if not job:
            raise HTTPException(404, 'Analysis job not found.')
        require_matter(job['matter_id'])
        if job['fingerprint'] != fingerprint(app.state.intelligence, store, job['matter_id']):
            raise HTTPException(409, 'Documents or settings changed. Start a fresh analysis.')
        if job['status'] not in {'paused', 'queued', 'running'}:
            raise HTTPException(409, 'This job cannot be resumed. Start a fresh analysis.')
        if job['status'] == 'paused' and (not job.get('retry_at') or datetime.fromisoformat(job['retry_at']) <= datetime.now(timezone.utc)):
            job.update(status='queued', message='Resuming saved analysis steps.')
            store.save_analysis_job(job)
        tasks.add_task(run_job, app.state.intelligence, store, job_id)
        return public_job(store, job)

    @app.post("/api/case-analysis/termination/evidence")
    def termination_evidence(payload: CaseRequest):
        require_matter(payload.matter_id)
        return evidence_candidates(store, payload.matter_id)

    @app.post("/api/case-analysis/termination")
    def termination_analysis(payload: TerminationRequest):
        require_matter(payload.matter_id)
        report = (compare_after_manual_review(app.state.intelligence, store, payload) if payload.role_review_id
                  else compare_termination(app.state.intelligence, store, payload))
        return store.save_report("case_analysis", payload.matter_id, ISSUE, report)

    @app.post('/api/case-analysis/termination/prepare')
    def prepare_termination(payload: AutomaticEvidenceRequest):
        require_matter(payload.matter_id)
        return prepare_evidence(app.state.intelligence, store, payload)

    @app.post('/api/case-analysis/termination/automatic')
    def automatic_termination(payload: AutomaticTerminationRequest):
        require_matter(payload.matter_id)
        report = compare_automatic(app.state.intelligence, store, payload)
        return store.save_report('case_analysis', payload.matter_id, ISSUE, report)

    @app.post("/api/case-analysis")
    def analyze_case(payload: CaseAnalysisRequest):
        require_matter(payload.matter_id)
        raise HTTPException(409, "General Analysis is paused. Use Termination & Cure with reviewed contract and authority quotations for new claim-level drafts. Existing reports remain available.")

    @app.get("/api/reports")
    def reports():
        return store.reports()

    @app.post("/api/reports/{report_id}/verify")
    def verify_saved_report(report_id: str):
        report = store.report(report_id)
        if not report:
            raise HTTPException(404, "Report not found.")
        require_matter(report["matter_id"])
        payload = reverify_report(app.state.intelligence, store, report)
        return store.save_report(report["kind"], report["matter_id"], report["query"], payload)

    return app


app = create_app()
