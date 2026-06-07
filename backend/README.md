# AI Compliance Platform Backend

FastAPI backend for the AI Compliance Platform.

The backend exists so a future React + TypeScript frontend can call stable HTTP endpoints instead of importing Python files directly. Python remains responsible for document extraction, FAISS retrieval, audit logic, privacy review logic, and LLM calls.

## Architecture

```text
React + TypeScript frontend
        |
        v
FastAPI backend
        |
        v
Python services
        |
        v
FAISS indexes, source PDFs, extracted text, and Groq
```

The backend wraps the existing review modules:

```text
document_review.py       Privacy review workflow
document_review_fda.py   FDA AI device audit workflow
document_reader.py       Original Streamlit document reader
```

The backend also has its own upload extraction service in `app/services/pdf_service.py` so API uploads can be handled cleanly.

## Run Locally

From the project root:

```powershell
.\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\venv\Scripts\uvicorn.exe backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000/docs
```

## Environment

The backend reads `GROQ_API_KEY` from `.env` in the project root or from the server environment.

Optional CORS setting:

```text
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:3000,http://localhost:3000
```

## Initial Endpoints

```text
GET  /api/health
GET  /api/fda-audit/devices
POST /api/fda-audit/upload
POST /api/fda-audit/devices/{filename}
POST /api/fda-audit/jobs/upload
POST /api/fda-audit/jobs/devices/{filename}
GET  /api/fda-audit/jobs
GET  /api/fda-audit/jobs/{job_id}
POST /api/privacy-review/upload
POST /api/workflows/fda-audit/mock
POST /api/workflows/fda-audit/devices/{filename}
```

## Endpoint Meaning

```text
GET /api/fda-audit/devices
```

Lists cleaned FDA device files already available under `data/fda_ai/devices/cleaned/`.

```text
POST /api/fda-audit/devices/{filename}
```

Runs an FDA audit against one existing cleaned device file.

```text
POST /api/fda-audit/upload
```

Runs an FDA audit against a newly uploaded PDF, DOCX, or TXT file.

```text
POST /api/fda-audit/jobs/upload
```

Creates a background FDA audit job for a newly uploaded file and immediately returns a `job_id`.

```text
POST /api/fda-audit/jobs/devices/{filename}
```

Creates a background FDA audit job for one existing cleaned device file.

```text
GET /api/fda-audit/jobs/{job_id}
```

Returns the current job state. Possible statuses are:

```text
queued
running
completed
failed
```

When a job is completed, the response includes the full FDA audit result.

```text
POST /api/privacy-review/upload
```

Runs a privacy policy or privacy notice review against HIPAA, CCPA, and HITECH.

## Background Job Flow

FDA audits can take a while because each audit runs multiple LLM calls. The job endpoints are designed for React:

```text
1. React uploads or selects a device.
2. FastAPI creates a job and returns job_id.
3. FastAPI runs the audit in the background.
4. React polls GET /api/fda-audit/jobs/{job_id}.
5. React renders the completed audit result.
```

Example job creation response:

```json
{
  "job_id": "d8e6f7a0-example",
  "status": "queued",
  "filename": "device_submission.pdf"
}
```

The current implementation uses an in-memory job store. That is fine for local development, but it resets when the server restarts. For AWS production, replace it with Redis, DynamoDB, RDS, SQS, or another persistent job system.

## React + TypeScript Integration

The future React frontend should call the backend through typed API helper functions, for example:

```text
frontend/src/api/client.ts
```

React should send uploads to FastAPI and render the returned JSON. It should not perform PDF extraction, FAISS retrieval, or LLM calls in the browser.

Expected frontend pages:

```text
PrivacyReview.tsx
FdaAudit.tsx
AuditHistory.tsx
```

Expected backend role:

```text
Receive upload -> extract text -> run review/audit -> return structured JSON
```

For long FDA audits, React should use the job endpoints instead of waiting for one long direct request.

## LangGraph Workflow Endpoints

The `langchain-workflow` branch adds experimental LangGraph endpoints for FDA audits:

```text
POST /api/workflows/fda-audit/mock
```

Runs a mock graph workflow without Groq calls. Use this to confirm orchestration, risk scoring, report generation, and escalation routing.

```text
POST /api/workflows/fda-audit/devices/{filename}
```

Runs the real graph workflow against an existing cleaned FDA device file. The response includes workflow status, overall risk, risk counts, escalation reasons, and the full audit report.
